# (c) grinchfox 2019

import bpy
from bpy.props import *

bl_info = {
    "name": "Baking Solution",
    "author": "grinchfox",
    "version": (0,1),
    "blender": (2,80,0),
    "location": "Render > Baking Solution",
    "description": "Simple baking organizer",
    "warning": "This addon is in early alpha stage",
    "wiki_url": "",
    "tracker_url": "https://github.com/grinchfox/baking_solution/issues",
    "support": 'COMMUNITY',
    "category": "Render"
}

# Settings

enum_channel_mask = (
    ('NONE', "None", ''),
    ('ROUGHNESS', "Roughness", ''),
    ('METALLIC', "Metallic", ''),
    ('AO', "Ambient Occlusion", ''))

enum_solution_modes = (
    ('COMBINED', "Combined", ''),
    ('DIFFUSE', "Diffuse", ''),
    ('MASKS', "Masks", ''),
    ('NORMAL',"Normal",''))

solution_bake_modes = {
    'COMBINED' : 'COMBINED',
    'DIFFUSE' : 'EMIT',
    'MASKS' : 'EMIT',
    'NORMAL' : 'NORMAL'}

enum_normal_direction = (
    ('POS_X', "+X", ''),
    ('POS_Y', "+Y", ''),
    ('POS_Z', "+Z", ''),
    ('NEG_X', "-X", ''),
    ('NEG_Y', "-Y", ''),
    ('NEG_Z', "-Z", ''))

def update_solution():
    update_node_solution()
    
def property_update(self, context):
    update_solution()

def check_empty_sources(self, context):
    for source in self:
        if source.object is None:
            self.remove(source)

class BakingSolutionImageTarget(bpy.types.PropertyGroup):
    """ Output image settings """
    image: PointerProperty(name = "Image Output", type = bpy.types.Image) # type: Image

class BakingSolutionImageTargets(bpy.types.PropertyGroup):
    COMBINED: PointerProperty(type = BakingSolutionImageTarget)
    DIFFUSE: PointerProperty(type = BakingSolutionImageTarget)
    MASKS: PointerProperty(type = BakingSolutionImageTarget)
    NORMAL: PointerProperty(type = BakingSolutionImageTarget)

class BakingSolutionNodeSettings(bpy.types.PropertyGroup):
    mask_r: EnumProperty(items = enum_channel_mask, default = 'AO', update = property_update)
    mask_g: EnumProperty(items = enum_channel_mask, default = 'ROUGHNESS', update = property_update)
    mask_b: EnumProperty(items = enum_channel_mask, default = 'METALLIC', update = property_update)
    normal_r: EnumProperty(items = enum_normal_direction, default = 'POS_X', update = property_update)
    normal_g: EnumProperty(items = enum_normal_direction, default = 'POS_Y', update = property_update)
    normal_b: EnumProperty(items = enum_normal_direction, default = 'POS_Z', update = property_update)
    normal_preview_low_range: BoolProperty(name = "Low Range", default = False, update = property_update)
    normal_tangent_space: BoolProperty(name = "Tangent Space", default = True, update = property_update)

class BakingSource(bpy.types.PropertyGroup):
    object: PointerProperty(type = bpy.types.Object)
    is_enabled: BoolProperty(default = True)

class BakingGroup(bpy.types.PropertyGroup):
    sources: CollectionProperty(type = BakingSource)
    target: PointerProperty(type = bpy.types.Object)
    cage_object: PointerProperty(type = bpy.types.Object)
    cage_extrusion: FloatProperty(default = 0, soft_min = 0)
    solution_settings: PointerProperty(type = BakingSolutionNodeSettings)
    image_targets: PointerProperty(type = BakingSolutionImageTargets)

class BakingSolutionSettings(bpy.types.PropertyGroup):
    solution_mode: EnumProperty(
        description = "BakingSolution node mode",
        items = enum_solution_modes,
        default = 'COMBINED',
        update = property_update)
    groups: CollectionProperty(type = BakingGroup)
    group_index: IntProperty(default = -1)
    solution_defaults: PointerProperty(type = BakingSolutionNodeSettings)
    
    @property
    def active_group(self):
        if self.group_index < 0 or self.group_index >= len(self.groups):
            return None
        return self.groups[self.group_index]

    @property
    def active_solution_settings(self):
        group = self.active_group
        if group is not None:
            return group.solution_settings
        else:
            return self.solution_defaults

# Operators

class OperatorAddGroup(bpy.types.Operator):
    bl_idname = 'baking_solution.add_group'
    bl_label = "Baking Solution: Add group"
    
    from_selected_and_active: BoolProperty(default = False)
    
    def execute(self, context):
        settings = context.scene.baking_solution
        selection = context.selected_objects
        active = context.active_object
        if self.from_selected_and_active and active is None:
            return {'CANCEL'}
        
        new_group = settings.groups.add()
        if self.from_selected_and_active:
            new_group.target = active
            for obj in selection:
                if obj != active:
                    newobj = new_group.sources.add()
                    newobj.object = obj
        return {'FINISHED'}
    
class OperatorRemoveCurrentGroup(bpy.types.Operator):
    bl_idname = 'baking_solution.remove_current_group'
    bl_label = "Remove baking group"
    
    @classmethod
    def poll(cls, context):
        return context.scene.baking_solution.active_group is not None
    
    def execute(self, context):
        settings = context.scene.baking_solution
        settings.groups.remove(settings.group_index)
        return {'FINISHED'}

def add_object_to_sources(sources, object):
    for source in sources:
        if source.object == object:
            source.is_enabled = True
            return
    source = sources.add()
    source.object = object

class OperatorAddSelectedToActiveGroup(bpy.types.Operator):
    bl_idname = 'baking_solution.add_selected_to_active_group'
    bl_label = "Baking Solution: Add selected to active group"
    
    def execute(self, context):
        settings = context.scene.baking_solution
        group = settings.groups[settings.group_index]
        if group is None:
            return {'ERROR', "No active group selected"}
        for object in context.selected_objects:
            add_object_to_sources(group.sources, object)
        return {'FINISHED'}

class OperatorRemoveFromActiveGroup(bpy.types.Operator):
    bl_idname = 'baking_solution.remove_from_active_group'
    bl_label = "Remove"
    
    remove_index: IntProperty(default = -1)
    
    def execute(self, context):
        settings = context.scene.baking_solution
        group = settings.groups[settings.group_index]
        if group is None:
            return {'CANCELLED', "No active group selected"}
        if self.remove_index == -1:
            return {'CANCELLED', "No valid property to remove"}
        group.sources.remove(self.remove_index)
        return {'FINISHED'}
        
class OperatorBake(bpy.types.Operator):
    bl_idname = 'baking_solution.bake'
    bl_label = "Bake"
    
    @classmethod
    def poll(cls, context):
        return context.scene.baking_solution.active_group is not None
    
    def execute(self, context):
        settings = context.scene.baking_solution
        render = context.scene.render
        group = settings.groups[settings.group_index]
        solution_settings = settings.active_solution_settings
        #render.bake.use_selected_to_active = True
        bpy.ops.object.select_all(action='DESELECT')
        for source in group.sources:
            if source.object is not None:
                source.object.select_set(source.is_enabled)
            #for obj in context.scene.objects:
            #    obj.select_set(source.object == obj)
                #print("Select {} = {}".format(obj.name, obj == source.object))
        #context.scene.objects_active = group.target
        group.target.select_set(True)
        context.view_layer.objects.active = group.target
        # Find target image and select its node
        target_image = getattr(group.image_targets, settings.solution_mode, None)
        if target_image is not None:
            for mat in group.target.data.materials:
                for node in mat.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image == target_image.image:
                        mat.node_tree.nodes.active = node
#        self.report({'INFO'}, "Baking...")
        bpy.ops.object.bake('INVOKE_DEFAULT',
            type=solution_bake_modes[settings.solution_mode],
            use_selected_to_active = True,
            cage_extrusion = group.cage_extrusion,
            use_clear = True,
            normal_r = solution_settings.normal_r,
            normal_g = solution_settings.normal_g,
            normal_b = solution_settings.normal_b,
            normal_space = solution_settings.normal_tangent_space and 'TANGENT' or 'OBJECT',
            cage_object = group.cage_object and group.cage_object.name or "",
            use_cage = group.cage_object is not None
        )
        return {'FINISHED'}
    
class OperatorResetNodePropToDefaults(bpy.types.Operator):
    bl_idname = 'baking_solution.reset_node_prop'
    bl_label = "Reset"
    
    prop = StringProperty()
    
    def execute(self, context):
        default_data = context.scene.baking_solution.solution_defaults
        data = context.scene.baking_solution.active_group.solution_settings
        setattr(data,self.prop, getattr(default_data,self.prop))
        return {'FINISHED'}

class OperatorUpdateNodeSolution(bpy.types.Operator):
    bl_idname = 'baking_solution.update_node_solution'
    bl_label = "Update Solution Node"
    
    def execute(self, context):
        update_node_solution()

# Node Graph

def update_node_solution():
    context = bpy.context
    scene = getattr(context,"scene", bpy.data.scenes[0])
    settings = scene.baking_solution
    solution_settings = settings.active_solution_settings
    
    node_bake_solution = bpy.data.node_groups.get("BakingSolution")
    if node_bake_solution is None:
        node_bake_solution = bpy.data.node_groups.new("BakingSolution","ShaderNodeTree")
        
    def clear_tree(tree):
        for i in tree.keys():
            tree.remove(tree.get(i))

    def tree_get_or_create(tree, type, name):
        node = tree.get(name)
        if node is None or node.bl_socket_idname != type:
            if not node is None:
                tree.remove(node)
            print("(Re)creating {} to {} {}".format(node, type, name))
            node = tree.new(type, name)
        return node
    
    nodes = node_bake_solution.nodes
    inputs = node_bake_solution.inputs
    outputs = node_bake_solution.outputs
    links = node_bake_solution.links
    clear_tree(nodes)
    in_diffuse = tree_get_or_create(inputs, "NodeSocketColor", "Diffuse")
    in_diffuse.default_value = (0.5, 0.5, 0.5, 1.0)
    in_roughness = tree_get_or_create(inputs, "NodeSocketFloat", "Roughness")
    in_roughness.default_value = 0.5
    in_roughness.min_value = 0.0
    in_roughness.max_value = 1.0
    in_metallic = tree_get_or_create(inputs, "NodeSocketFloat", "Metallic")
    in_metallic.default_value = 0.0
    in_metallic.min_value = 0.0
    in_metallic.max_value = 1.0
    out_shader = tree_get_or_create(outputs, "NodeSocketShader", "Shader")
    #print(node_bake_solution.inputs.keys())
    node_in = nodes.new("NodeGroupInput")
    node_out = nodes.new("NodeGroupOutput")
    node_out.location = (1000,0)
    
    mode = settings.solution_mode
    if mode == 'COMBINED': # Preview shader pipeline
        node_principled = nodes.new("ShaderNodeBsdfPrincipled")
        node_principled.location = (300,0)
        node_principled.label = "Preview"
        links.new(node_in.outputs[in_diffuse.name], node_principled.inputs["Base Color"])
        links.new(node_in.outputs[in_roughness.name], node_principled.inputs["Roughness"])
        links.new(node_in.outputs[in_metallic.name], node_principled.inputs["Metallic"])
        links.new(node_out.inputs[out_shader.name], node_principled.outputs["BSDF"])
    elif mode == 'DIFFUSE': # Diffuse bake shader pipeline (it is needed because metallic kills diffuse)
        node_emit = nodes.new("ShaderNodeEmission")
        node_emit.location = (300, 0)
        links.new(node_in.outputs[in_diffuse.name], node_emit.inputs["Color"])
        links.new(node_emit.outputs["Emission"], node_out.inputs[out_shader.name])
    elif mode == 'MASKS': # Masks bake shader pipeline
        node_ao = nodes.new("ShaderNodeAmbientOcclusion")
        node_ao.location = (300,-200)
        node_combine = nodes.new("ShaderNodeCombineRGB")
        node_combine.location = (500,0)
        out_links = {
            'ROUGHNESS': node_in.outputs[in_roughness.name],
            'METALLIC': node_in.outputs[in_metallic.name],
            'AO': node_ao.outputs["AO"]}
        if solution_settings.mask_r != 'NONE':
            links.new(out_links[solution_settings.mask_r], node_combine.inputs["R"])
        if solution_settings.mask_g != 'NONE':
            links.new(out_links[solution_settings.mask_g], node_combine.inputs["G"])
        if solution_settings.mask_b != 'NONE':
            links.new(out_links[solution_settings.mask_b], node_combine.inputs["B"])
        links.new(node_out.inputs[out_shader.name], node_combine.outputs["Image"])
    elif mode == 'NORMAL': # Normal map preview
        node_bump = nodes.new("ShaderNodeBump")
        node_bump.location = (400, 400)
        node_combine = nodes.new("ShaderNodeCombineRGB")
        node_combine.location = (1000,0)
        color_links = {}
        if solution_settings.normal_tangent_space:
            node_geometry = nodes.new("ShaderNodeNewGeometry")
            node_geometry.location = (200, 0)
            node_tgv = nodes.new("ShaderNodeVectorMath")
            node_tgv.location = (400, 200)
            node_tgv.operation = 'CROSS_PRODUCT'
            node_nx = nodes.new("ShaderNodeVectorMath")
            node_nx.location = (600, 400)
            node_nx.operation = 'DOT_PRODUCT'
            node_ny = nodes.new("ShaderNodeVectorMath")
            node_ny.location = (600, 200)
            node_ny.operation = 'DOT_PRODUCT'
            node_nz = nodes.new("ShaderNodeVectorMath")
            node_nz.location = (600, 0)
            node_nz.operation = 'DOT_PRODUCT'
            links.new(node_tgv.inputs[0], node_geometry.outputs["Tangent"])
            links.new(node_tgv.inputs[1], node_geometry.outputs["Normal"])
            links.new(node_nx.inputs[0], node_bump.outputs["Normal"])
            links.new(node_nx.inputs[1], node_geometry.outputs["Tangent"])
            links.new(node_ny.inputs[0], node_bump.outputs["Normal"])
            links.new(node_ny.inputs[1], node_tgv.outputs[0])
            links.new(node_nz.inputs[0], node_bump.outputs["Normal"])
            links.new(node_nz.inputs[1], node_geometry.outputs["Normal"])
            color_links["X"] = node_nx.outputs[1]
            color_links["Y"] = node_ny.outputs[1]
            color_links["Z"] = node_nz.outputs[1]
        else:
            node_separate = nodes.new("ShaderNodeSeparateXYZ")
            node_separate.location = (600,0)
            links.new(node_bump.outputs["Normal"], node_separate.inputs[0])
            color_links["X"] = node_separate.outputs["X"]
            color_links["Y"] = node_separate.outputs["Y"]
            color_links["Z"] = node_separate.outputs["Z"]
        axis_map = {'POS_X':'X','POS_Y':'Y','POS_Z':'Z','NEG_X':'X','NEG_Y':'Y','NEG_Z':'Z'}
        loc_y = 200
        for normal_dir, link_name in ((solution_settings.normal_r, "R"),(solution_settings.normal_g, "G"),(solution_settings.normal_b, "B")):
            if normal_dir in ['NEG_X','NEG_Y','NEG_Z']:
                node_neg = nodes.new("ShaderNodeMath")
                node_neg.location = (800, loc_y)
                node_neg.operation = 'MULTIPLY'
                node_neg.inputs[1].default_value = -1
                links.new(node_neg.inputs[0], color_links[axis_map[normal_dir]])
                links.new(node_neg.outputs[0], node_combine.inputs[link_name])
            else:
                links.new(color_links[axis_map[normal_dir]], node_combine.inputs[link_name])
            loc_y -= 200
        node_emit = nodes.new("ShaderNodeEmission")
        node_emit.location = (1600, 0)
        node_out.location = (1800, 0)
        if solution_settings.normal_preview_low_range:
            node_norm1 = nodes.new("ShaderNodeMixRGB")
            node_norm1.location = (1200, 0)
            node_norm1.inputs[0].default_value = 1
            node_norm1.inputs[2].default_value = (1,1,1,1)
            node_norm1.blend_type = 'ADD'
            node_norm2 = nodes.new("ShaderNodeMixRGB")
            node_norm2.location = (1400, 0)
            node_norm2.inputs[0].default_value = 1
            node_norm2.inputs[2].default_value = (0.5,0.5,0.5,1)
            node_norm2.blend_type = 'MULTIPLY'
            links.new(node_norm1.inputs[1], node_combine.outputs["Image"])
            links.new(node_norm2.inputs[1], node_norm1.outputs["Color"])
            links.new(node_emit.inputs["Color"], node_norm2.outputs["Color"])
        else:
            links.new(node_emit.inputs["Color"], node_combine.outputs["Image"])
        links.new(node_emit.outputs["Emission"], node_out.inputs[out_shader.name])
        pass
    else:
        raise Exception("Unknown solution mode {}".format(mode))

class BakingSolution_UL_BakingGroup(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        #split = layout.split()
        if item.target is None:
            layout.label(text = "No Target")
        else:
            #split.template_icon()
            #split.icon(item.target)
            layout.label(text = item.target.name, icon_value = layout.icon(item.target))#'OBJECT_DATA')
        #split.prop(item, 'target', text = "", emboss = False)
        #split.template_ID(item, 'target')
        #split.prop(item, 'sources', text = "") #split.label(text = "{} objects".format(item.sources))
    
    def invoke(self, context, event):
        pass

def prop_defaults(layout, data, property, default_data, **kwargs):
    row = layout.row()
    row.prop(data, property, **kwargs)
    op = row.operator('baking_solution.reset_node_prop', text = "", icon = 'LOOP_BACK', emboss = getattr(data, property) != getattr(default_data, property))
    op.prop = property
    
class LayoutBakingPanel(bpy.types.Panel):
    bl_label = "Baking Solution"
    bl_idname = "RENDER_PT_baking_solution"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.baking_solution
        node_settings = settings.active_solution_settings
        node_defaults = settings.solution_defaults
        
        if bpy.data.node_groups.get("BakingSolution") is None:
            box = layout.box()
            box.label(text = "Click this button to genereate solution node group", icon = 'INFO')
            box.operator("baking_solution.update_node_solution")
        
        row = layout.row(align = True)
        row.template_list('BakingSolution_UL_BakingGroup', "", settings, "groups", settings, "group_index", rows=2)
        group = settings.active_group
        if not group is None:
            box = row.box()
            box.alignment = 'EXPAND'
            box.prop(group, 'target', text = "Target")
            box.prop(group, 'cage_object', text = "Cage")
            box.prop(group, 'cage_extrusion', text = "Cage Extrusion")
            if len(group.sources) == 0:
                box.label(text = "No source objects")
            else:
                box.label(text = "Source objects:")
                list = box.column()
                obj_id = 0
                for source in group.sources:
                    object_row = list.row(align = True)
                    #object_row.label(text = "[{}]".format(obj_id))
                    #object_row.prop(obj, 'object', text = "")
                    object_row.label(text = source.object.name, icon_value = layout.icon(source.object))#'OBJECT_DATA')
                    object_row.prop(source, 'is_enabled', text="", icon = source.is_enabled and 'RESTRICT_RENDER_OFF' or 'RESTRICT_RENDER_ON', emboss = False)
                    op_remove = object_row.operator('baking_solution.remove_from_active_group', text = "", icon = 'X', emboss = False)
                    op_remove.remove_index = obj_id
                    obj_id += 1
            box.operator('baking_solution.add_selected_to_active_group', text = "Add Selected", icon = 'ADD')
        
        col = layout.column(align = True)
        row = col.row(align = True)
        op_add = row.operator('baking_solution.add_group', text = "New Group", icon = 'ADD')
        op_remove = row.operator('baking_solution.remove_current_group', text = "Remove Group", icon = 'REMOVE')
        op_add_from_selected = col.operator('baking_solution.add_group', text = "New Group from Selected and Active", icon = 'ADD')
        op_add_from_selected.from_selected_and_active = True
        
        row = layout.row()
        row.scale_y = 2
        row.operator('baking_solution.bake', text = "Bake Selected", icon = 'RENDER_STILL')
        
        layout.label(text = "Solution Mode:")
        layout.prop(settings, 'solution_mode', expand = True)
        
        if group is not None:
            image_target = getattr(group.image_targets, settings.solution_mode, None)
            if image_target is not None:
                layout.prop(image_target, "image")
        
        if settings.solution_mode == 'MASKS':
            layout.label(text = "Mask Channels:")
            box = layout.box()
            #row = box.row()
            #row.label(text = "", icon = 'COLOR_RED')
            prop_defaults(box, node_settings, 'mask_r', node_defaults, text = "", icon = 'COLOR_RED', expand = False)
            #row = box.row()
            #row.label(text = "", icon = 'COLOR_GREEN')
            prop_defaults(box, node_settings, 'mask_g', node_defaults, text = "", icon = 'COLOR_GREEN', expand = False)
            #row = box.row()
            #row.label(text = "", icon = 'COLOR_BLUE')
            prop_defaults(box, node_settings, 'mask_b', node_defaults, text = "", icon = 'COLOR_BLUE', expand = False)
        elif settings.solution_mode == 'NORMAL':
            layout.label(text = "Normal Channels:")
            box = layout.box()
            row = box.row()
            row.label(text = "", icon = 'COLOR_RED')
            prop_defaults(row, node_settings, 'normal_r', node_defaults, expand = True)
            row = box.row()
            row.label(text = "", icon = 'COLOR_GREEN')
            prop_defaults(row, node_settings, 'normal_g', node_defaults, expand = True)
            row = box.row()
            row.label(text = "", icon = 'COLOR_BLUE')
            prop_defaults(row, node_settings, 'normal_b', node_defaults, expand = True)
            prop_defaults(box, node_settings, 'normal_tangent_space', node_defaults, expand = True)
            layout.label(text = "Preview Settings:")
            box = layout.box()
            prop_defaults(box, node_settings, 'normal_preview_low_range', node_defaults)
            
        

def register():
    bpy.utils.register_class(BakingSolutionImageTarget)
    bpy.utils.register_class(BakingSolutionImageTargets)
    bpy.utils.register_class(BakingSolutionNodeSettings)
    bpy.utils.register_class(BakingSource)
    bpy.utils.register_class(BakingGroup)
    bpy.utils.register_class(BakingSolutionSettings)
    bpy.utils.register_class(OperatorAddGroup)
    bpy.utils.register_class(OperatorRemoveCurrentGroup)
    bpy.utils.register_class(OperatorAddSelectedToActiveGroup)
    bpy.utils.register_class(OperatorRemoveFromActiveGroup)
    bpy.utils.register_class(OperatorBake)
    bpy.utils.register_class(OperatorResetNodePropToDefaults)
    bpy.utils.register_class(OperatorUpdateNodeSolution)
    bpy.utils.register_class(BakingSolution_UL_BakingGroup)
    bpy.utils.register_class(LayoutBakingPanel)
    bpy.types.Scene.baking_solution = bpy.props.PointerProperty(type = BakingSolutionSettings)
    
    #update_solution()
    
def unregister():
    bpy.utils.unregister_class(BakingSolutionImageTarget)
    bpy.utils.unregister_class(BakingSolutionImageTargets)
    bpy.utils.unregister_class(BakingSolutionNodeSettings)
    bpy.utils.unregister_class(BakingSource)
    bpy.utils.unregister_class(BakingGroup)
    bpy.utils.unregister_class(BakingSolutionSettings)
    bpy.utils.unregister_class(OperatorAddGroup)
    bpy.utils.unregister_class(OperatorRemoveCurrentGroup)
    bpy.utils.unregister_class(OperatorAddSelectedToActiveGroup)
    bpy.utils.unregister_class(OperatorRemoveFromActiveGroup)
    bpy.utils.unregister_class(OperatorBake)
    bpy.utils.unregister_class(OperatorResetNodePropToDefaults)
    bpy.utils.unregister_class(OperatorUpdateNodeSolution)
    bpy.utils.unregister_class(BakingSolution_UL_BakingGroup)
    bpy.utils.unregister_class(LayoutBakingPanel)
    
if __name__ == "__main__":
    register()