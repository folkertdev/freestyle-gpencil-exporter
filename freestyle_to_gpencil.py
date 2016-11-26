from freestyle.shaders import *
from freestyle.predicates import *
from freestyle.types import Operators, StrokeShader, StrokeVertex
from freestyle.chainingiterators import ChainSilhouetteIterator, ChainPredicateIterator
from freestyle.functions import *

import bpy
from bpy_extras import view3d_utils
import bpy_extras
from mathutils import Vector, Matrix
import functools
import collections
import sys

bl_info = {
    "name": "Freestyle to Grease Pencil",
    "author": "Folkert de Vries",
    "version": (1, 0),
    "blender": (2, 74, 1),
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
        IntProperty,
        )
import parameter_editor


def get_strokes():
    # a tuple containing all strokes from the current render. should get replaced by freestyle.context at some point

    return tuple(map(Operators().get_stroke_from_index, range(Operators().get_strokes_size())))
# get the exact scene dimensions
def render_height(scene):
    return int(scene.render.resolution_y * scene.render.resolution_percentage / 100)

def render_width(scene):
    return int(scene.render.resolution_x * scene.render.resolution_percentage / 100)

def render_dimensions(scene):
    return render_width(scene), render_height(scene)

class FreestyleGPencil(bpy.types.PropertyGroup):
    """Implements the properties for the Freestyle to Grease Pencil exporter"""
    bl_idname = "RENDER_PT_gpencil_export"

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
    write_mode = EnumProperty(
            name="Write Mode",
            items=(
                ('Keep', "Keep", "Add new GP strokes to the current layer"),
                ('OVERWRITE', "Overwrite", "Overwrite the current layer"),
                # ('OVERWRITEFRAME', "Overwrite Frame", "Only overwrite the current layer if it is the same frame"),
                ),
            default='OVERWRITE'
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
        row.prop(gp, "write_mode", expand=True)


class FSGPExporterLinesetPanel(bpy.types.Panel):
    """Creates a Panel in the Render Layers context of the properties editor"""
    bl_idname = "RENDER_PT_FSGPExporterLinesetPanel"
    bl_space_type = 'PROPERTIES'
    bl_label = "Freestyle Line Style Grease Pencil Export"
    bl_region_type = 'WINDOW'
    bl_context = "render_layer"

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        gp = scene.freestyle_gpencil_export
        freestyle = scene.render.layers.active.freestyle_settings
        linestyle = freestyle.linesets.active.linestyle

        layout.active = (gp.use_freestyle_gpencil_export and freestyle.mode != 'SCRIPT')

        row = layout.row()
        column = row.column()
        column.prop(linestyle, 'use_extract_thickness')

        column = row.column()
        column.prop(linestyle, 'use_extract_alpha')

        row = layout.row()
        row.prop(linestyle, "extract_color", expand=True)


def render_visible_strokes():
    """Renders the scene, selects visible strokes and returns them as a tuple"""
    upred = QuantitativeInvisibilityUP1D(0) # visible lines only
    #upred = TrueUP1D() # all lines
    Operators.select(upred)
    Operators.bidirectional_chain(ChainSilhouetteIterator(), NotUP1D(upred))
    Operators.create(TrueUP1D(), [])
    return get_strokes()

def render_external_contour():
    """Renders the scene, selects visible strokes of the Contour nature and returns them as a tuple"""
    upred = AndUP1D(QuantitativeInvisibilityUP1D(0), ContourUP1D())
    Operators.select(upred)
    # chain when the same shape and visible
    bpred = SameShapeIdBP1D()
    Operators.bidirectional_chain(ChainPredicateIterator(upred, bpred), NotUP1D(upred))
    Operators.create(TrueUP1D(), [])
    return get_strokes()


def create_gpencil_layer(scene, name, color, alpha, fill_color, fill_alpha):
    """Creates a new GPencil layer (if needed) to store the Freestyle result"""

    try:
        gp = bpy.data.grease_pencil.values()[0]
    except IndexError:
        gp = bpy.data.grease_pencil.new(name="GPencil")

    scene.grease_pencil = gp
    layer = gp.layers.get(name, False)

    if not layer:
        print("making new GPencil layer")
        layer = gp.layers.new(name=name, set_active=True)

    elif scene.freestyle_gpencil_export.write_mode == 'OVERWRITE':
        # empty the current strokes from the gp layer
        layer.clear()

    """
    elif scene.freestyle_gpencil_export.write_mode == 'OVERWRITEFRAME':
        # empty the current strokes from the gp layer
        print("parsed layer", layer.info[-6:],int(layer.info[-6:]), scene.frame_current)
        if int(layer.info[-6:]) == scene.frame_current: 
            layer.clear()
    """


    # can this be done more neatly? layer.frames.get(..., ...) doesn't seem to work
    frame = frame_from_frame_number(layer, scene.frame_current) or layer.frames.new(scene.frame_current)
    return layer, frame 

def frame_from_frame_number(layer, current_frame):
    """Get a reference to the current frame if it exists, else False"""
    return next((frame for frame in layer.frames if frame.frame_number == current_frame), False)

def rgb_to_hex(rgb):
    """Used to compare by hex. loses some precision, which is exactly what we want"""
    return '#%02x%02x%02x' % rgb

def color_to_hex(color):
    return rgb_to_hex(tuple(int(v) for v in (color.r, color.g, color.b)))


def get_colorname(cache, key, palette, name="FSGPencilColor"):
    code = color_to_hex(key)
    try:
        color = cache[code]

    except KeyError:
        color = palette.colors.new()
        color.name = name
        color.color = key
        color.alpha = 1.0
        cache[code] = color

    return (cache, color.name)



DrawOptions = collections.namedtuple('DrawOptions', 'draw_mode color_extraction thickness_extraction alpha_extraction')

def freestyle_to_gpencil_strokes(strokes, frame, lineset, options): # draw_mode='3DSPACE', color_extraction='BASE'):
    mat = bpy.context.scene.camera.matrix_local.copy()

    # pick the active palette or create a default one
    grease_pencil = bpy.context.scene.grease_pencil
    palette = grease_pencil.palettes.active or grease_pencil.palettes.new("GP_Palette")

    # can we tag the colors the script adds, to remove them when they are not used? 
    cache = { color_to_hex(color.color) : color for color in palette.colors if color.fsgpexporter } 

    # keep track of which colors are used (to remove unused ones)
    used = []


    for fstroke in strokes:

        if options.color_extraction == 'FIRST':
            base_color = fstroke[0].attribute.color
        elif options.color_extraction == 'FINAL':
            base_color = fstroke[-1].attribute.color
        else:
            base_color = lineset.linestyle.color

        # color has to be frozen (immutable) for it to be stored
        base_color.freeze()

        (cache, colorname) = get_colorname(cache, base_color, palette) 

        # append the current color, so it is kept
        used.append(colorname)

        gpstroke = frame.strokes.new(colorname=colorname)
        gpstroke.draw_mode = options.draw_mode
        gpstroke.points.add(count=len(fstroke), pressure=1, strength=1)

        # the max width gets pressure 1.0. Smaller widths get a pressure 0 <= x < 1 
        base_width = functools.reduce(max, (sum(svert.attribute.thickness) for svert in fstroke)) 

        # set the default (pressure == 1) width for the gpstroke
        gpstroke.line_width = base_width 

        if options.draw_mode == '3DSPACE':
            for svert, point in zip (fstroke, gpstroke.points):
                point.co = mat * svert.point_3d

                if options.thickness_extraction:
                    point.pressure = sum(svert.attribute.thickness) / max(1e-6, base_width)

                if options.alpha_extraction:
                    point.strength = svert.attribute.alpha

        elif options.draw_mode == 'SCREEN':
            gpstroke.draw_mode = '2DSPACE'
            width, height = render_dimensions(bpy.context.scene)
            for svert, point in zip (fstroke, gpstroke.points):
                x, y = svert.point
                point.co = Vector((abs(x / width), abs(y / height), 0.0)) * 100
                point.strength = svert.attribute.alpha

        else:
            raise NotImplementedError()

    # remove unneeded colors
    for color in palette.colors:
        if color.fsgpexporter and color.name not in used:
            palette.colors.remove(color)


def freestyle_to_fill(scene, lineset):
    default = dict(color=(0, 0, 0), alpha=1, fill_color=(0, 1, 0), fill_alpha=1)
    layer, frame = create_gpencil_layer(scene, "FF " + lineset.name, **default)
    # render the external contour 
    strokes = render_external_contour()
    freestyle_to_gpencil_strokes(strokes, frame, lineset, draw_mode=scene.freestyle_gpencil_export.draw_mode)

def freestyle_to_strokes(scene, lineset):
    default = dict(color=(0, 0, 0), alpha=1, fill_color=(0, 1, 0), fill_alpha=0)

    # name = "FS {} f{:06}".format(lineset.name, scene.frame_current)
    name = "FS {}".format(lineset.name)
    layer, frame = create_gpencil_layer(scene, name, **default)
    # render the normal strokes 
    #strokes = render_visible_strokes()
    strokes = get_strokes()

    exporter = scene.freestyle_gpencil_export
    linestyle = lineset.linestyle

    options = DrawOptions(draw_mode= exporter.draw_mode
            , color_extraction = linestyle.extract_color
            , alpha_extraction = linestyle.use_extract_alpha
            , thickness_extraction = linestyle.use_extract_thickness
            )
    freestyle_to_gpencil_strokes(strokes, frame, lineset, options)


classes = (
    FreestyleGPencil,
    SVGExporterPanel,
    FSGPExporterLinesetPanel,
    )

def export_stroke(scene, _, lineset):
    # create stroke layer
    freestyle_to_strokes(scene, lineset)

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


    linestyle = bpy.types.FreestyleLineStyle
    linestyle.use_extract_thickness = BoolProperty(
            name="Extract Thickness",
            description="Apply Freestyle thickness values to Grease Pencil strokes",
            default=True,
            )
    linestyle.use_extract_alpha = BoolProperty(
            name="Extract Alpha",
            description="Apply Freestyle alpha values to Grease Pencil strokes",
            default=True,
            )
    linestyle.extract_color= EnumProperty(
            name="Stroke Color Mode",
            items=(
                ('NONE', "None", "Don't extract color"),
                ('BASE', "Base Color", "Use the linestyle's base color"),
                ('FIRST', "First Vertex", "Use the color of a stroke's first vertex"),
                ('FINAL', "Final Vertex", "Use the color of a stroke's final vertex"),
                ),
            default='BASE'
            )


    bpy.types.GPencilPaletteColor.fsgpexporter = BoolProperty(name="Owned by FSGPExporter"
            , description="Was this color created by the freestyle gpencil exporter?"
            , default=False
            , options = { 'ANIMATABLE' } 
            )


    # doesn't work because GPencilLayer is not a subclass of bpy.types.ID
    bpy.types.GPencilLayer.frame = IntProperty(
            decription="The frame associated with this GP layer by the FS GP exporter"
            , default = sys.maxsize
            )

    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.freestyle_gpencil_export = PointerProperty(type=FreestyleGPencil)

    parameter_editor.callbacks_lineset_pre.append(export_fill)
    parameter_editor.callbacks_lineset_post.append(export_stroke)
    # bpy.app.handlers.render_post.append(export_stroke)

def unregister():

    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.freestyle_gpencil_export
    del bpy.types.GPencilPaletteColor.fsgpexporter

    del bpy.types.FreestyleLineStyle.use_extract_thickness
    del bpy.types.FreestyleLineStyle.use_extract_alpha
    del bpy.types.FreestyleLineStyle.extract_color

    del bpy.types.GPencilLayer.frame

    parameter_editor.callbacks_lineset_pre.append(export_fill)
    parameter_editor.callbacks_lineset_post.remove(export_stroke)


if __name__ == '__main__':
    register()

