from freestyle.shaders import *
from freestyle.predicates import *
from freestyle.types import Operators, StrokeShader, StrokeVertex
from freestyle.chainingiterators import ChainSilhouetteIterator, ChainPredicateIterator
from freestyle.functions import *

import bpy
from bpy_extras import view3d_utils
import bpy_extras
from mathutils import Vector, Matrix

bl_info = {
    "name": "Freestyle to Grease Pencil",
    "author": "Folkert de Vries",
    "version": (1, 0),
    "blender": (2, 72, 1),
    "location": "Properties > Render > Freestyle to Grease Pencil",
    "description": "Exports Freestyle's stylized to a Grease Pencil sketch",
    "warning": "",
    "wiki_url": "",
    "category": "Render",
    }

from bpy.props import (
        BoolProperty,
        EnumProperty,
        PointerProperty,
        )
import parameter_editor


def get_strokes():
    return tuple(map(Operators().get_stroke_from_index, range(Operators().get_strokes_size())))

def render_height(scene):
    return int(scene.render.resolution_y * scene.render.resolution_percentage / 100)


def render_width(scene):
    return int(scene.render.resolution_x * scene.render.resolution_percentage / 100)

def render_dimensions(scene):
    return render_width(scene), render_height(scene)

class FreestyleGPencil(bpy.types.PropertyGroup):
    """Implements the properties for the Freestyle to Grease Pencil exporter"""
    bl_idname = "RENDER_PT_svg_export"

    use_freestyle_gpencil_export = BoolProperty(
            name="Grease Pencil Export",
            description="Export Freestyle edges to Grease Pencil",
            )
    draw_mode = EnumProperty(
            name="Draw Mode",
            items=(
                # ('2DSPACE', "2D Space", "Export a single frame", 0),
                ('3DSPACE', "3D Space", "Export an animation", 1),
                # ('2DIMAGE', "2D Image", "", 2),
                ('SCREEN', "Screen", "", 3),
                ),
            default='3DSPACE',
            )
    use_fill = BoolProperty(
            name="Fill Contours",
            description="Fill the contour with the object's material color",
            )


class SVGExporterPanel(bpy.types.Panel):
    """Creates a Panel in the render context of the properties editor"""
    bl_idname = "RENDER_PT_FreestyleGPencilPanel"
    bl_space_type = 'PROPERTIES'
    bl_label = "Freestyle to Grease Pencil"
    bl_region_type = 'WINDOW'
    bl_context = "render"

    def draw_header(self, context):
        self.layout.prop(context.scene.freestyle_gpencil_export, "use_freestyle_gpencil_export", text="")

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        gp = scene.freestyle_gpencil_export
        freestyle = scene.render.layers.active.freestyle_settings

        layout.active = (gp.use_freestyle_gpencil_export and freestyle.mode != 'SCRIPT')

        row = layout.row()
        row.prop(gp, "draw_mode", expand=True)

        row = layout.row()
        #row.prop(svg, "split_at_invisible")
        row.prop(gp, "use_fill")



def render_visible_strokes():
    upred = QuantitativeInvisibilityUP1D(0) # visible lines only
    #upred = TrueUP1D() # all lines
    Operators.select(upred)
    Operators.bidirectional_chain(ChainSilhouetteIterator(), NotUP1D(upred))
    Operators.create(TrueUP1D(), [])
    return get_strokes()

def render_external_contour():
    upred = AndUP1D(QuantitativeInvisibilityUP1D(0), ContourUP1D())
    Operators.select(upred)
    # chain when the same shape and visible
    bpred = SameShapeIdBP1D()
    Operators.bidirectional_chain(ChainPredicateIterator(upred, bpred), NotUP1D(upred))
    Operators.create(TrueUP1D(), [])
    return tuple(map(Operators.get_stroke_from_index, range(Operators.get_strokes_size())))


def create_gpencil_layer(scene, name, color, alpha, fill_color, fill_alpha):

    gp = bpy.data.grease_pencil.get("FreestyleGPencil", False) or bpy.data.grease_pencil.new(name="FreestyleGPencil")
    scene.grease_pencil = gp
    layer = gp.layers.get(name, False)
    if not layer:
        print("making new GPencil layer")
        layer = gp.layers.new(name=name, set_active=True)
        # set defaults
        layer.fill_color = fill_color
        layer.fill_alpha = fill_alpha
        layer.alpha = alpha 
        layer.color = color

    # can this be done more neatly? layer.frames.get(..., ...) doesn't seem to work
    frame = frame_from_frame_number(layer, scene.frame_current) or layer.frames.new(scene.frame_current)
    return layer, frame 

def frame_from_frame_number(layer, current_frame):
    return next((frame for frame in layer.frames if frame.frame_number == current_frame), False)

def freestyle_to_gpencil_strokes(strokes, frame, pressure=1, draw_mode='3DSPACE'):
    mat = bpy.context.scene.camera.matrix_local.copy()
    for fstroke in strokes:
        gpstroke = frame.strokes.new()
        # enum in ('SCREEN', '3DSPACE', '2DSPACE', '2DIMAGE')
        gpstroke.draw_mode = draw_mode
        gpstroke.points.add(count=len(fstroke))

        if draw_mode == '3DSPACE':
            for svert, point in zip(fstroke, gpstroke.points):
                point.co = mat * svert.point_3d
                point.pressure = pressure
        elif draw_mode == 'SCREEN':
            width, height = render_dimensions(bpy.context.scene)
            for svert, point in zip(fstroke, gpstroke.points):
                x, y = svert.point
                point.co = Vector((abs(x / width), abs(y / height), 0.0)) * 100
                point.pressure = 1
        else:
            raise NotImplementedError()


def freestyle_to_fill(scene):
    default = dict(color=(0, 0, 0), alpha=1, fill_color=(0, 1, 0), fill_alpha=1)
    layer, frame = create_gpencil_layer(scene, "freestyle fill", **default)
    # render the external contour 
    strokes = render_external_contour()
    freestyle_to_gpencil_strokes(strokes, frame, draw_mode=scene.freestyle_gpencil_export.draw_mode)

def freestyle_to_strokes(scene):
    default = dict(color=(0, 0, 0), alpha=1, fill_color=(0, 1, 0), fill_alpha=0)
    layer, frame = create_gpencil_layer(scene, "freestyle stroke", **default)
    # render the normal strokes 
    #strokes = render_visible_strokes()
    strokes = get_strokes()
    freestyle_to_gpencil_strokes(strokes, frame, draw_mode=scene.freestyle_gpencil_export.draw_mode)


classes = (
    FreestyleGPencil,
    SVGExporterPanel,
    )

def export_stroke(scene, layer, lineset):
    # create stroke layer
    freestyle_to_strokes(scene)

def export_fill(scene, layer, lineset):
    # Doesn't work for 3D due to concave edges
    return

    #if not scene.freestyle_gpencil_export.use_freestyle_gpencil_export:
    #    return 

    #if scene.freestyle_gpencil_export.use_fill:
    #    # create the fill layer
    #    freestyle_to_fill(scene)
    #    # delete these strokes
    #    Operators.reset(delete_strokes=True)



def register():

    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.freestyle_gpencil_export = PointerProperty(type=FreestyleGPencil)

    parameter_editor.callbacks_lineset_pre.append(export_fill)
    parameter_editor.callbacks_lineset_post.append(export_stroke)

def unregister():

    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.freestyle_gpencil_export

    parameter_editor.callbacks_lineset_pre.append(export_fill)
    parameter_editor.callbacks_lineset_post.remove(export_stroke)


if __name__ == '__main__':
    register()

