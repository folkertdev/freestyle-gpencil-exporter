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


DrawOptions = collections.namedtuple('DrawOptions', 'draw_mode color_extraction color_extraction_mode thickness_extraction alpha_extraction')


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

        column = layout.column()

        column.label(text="Draw Mode:")
        row = column.row()
        row.prop(gp, "draw_mode", expand=True)

        column.label(text="Write Mode:")
        row = column.row()
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
        exporter = scene.freestyle_gpencil_export
        freestyle = scene.render.layers.active.freestyle_settings
        linestyle = freestyle.linesets.active.linestyle

        layout.active = (exporter.use_freestyle_gpencil_export and freestyle.mode != 'SCRIPT')

        col = layout.column()
        col.label(text="Extract Freestyle Settings:")
        row = col.row(align=True)
        row.prop(linestyle, "use_extract_color", text="Stroke Color", toggle=True)
        # row.prop(linestyle, "use_extract_fill", text="Fill Color", toggle=True)
        row.prop(linestyle, "use_extract_thickness", text="Thickness", toggle=True)
        row.prop(linestyle, "use_extract_alpha", text="Alpha", toggle=True)

        if linestyle.use_extract_color:
            row = layout.row()
            row.label(text="Color Extraction Mode:")
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

    if not scene.grease_pencil:
        scene.grease_pencil = bpy.data.grease_pencil.new("GPencil")


    layer = scene.grease_pencil.layers.get(name, False)

    if not layer:
        layer = scene.grease_pencil.layers.new(name=name, set_active=True)

    elif scene.freestyle_gpencil_export.write_mode == 'OVERWRITE':
        # empty the current strokes from the gp layer
        layer.clear()

    # can this be done more neatly? layer.frames.get(..., ...) doesn't seem to work
    frame = frame_from_frame_number(layer, scene.frame_current) or layer.frames.new(scene.frame_current)
    return (layer, frame)

def frame_from_frame_number(layer, current_frame):
    """Get a reference to the current frame if it exists, else False"""
    return next((frame for frame in layer.frames if frame.frame_number == current_frame), False)

def rgb_to_hex(rgb):
    """Used to compare by hex. loses some precision, which is exactly what we want"""
    return '#%02x%02x%02x' % rgb

def color_to_hex(color):
    return rgb_to_hex(tuple(int(v) for v in (color.r, color.g, color.b)))


def diffuse_from_stroke(stroke, curvemat=CurveMaterialF0D()):
    material = curvemat(Interface0DIterator(stroke))
    return material.diffuse


def get_fill_color(stroke):
    *color, alpha = diffuse_from_stroke(stroke)
    color = tuple(int(255 * c) for c in color)


def get_colorname(colors, key, palette, name="FSGPencilColor"):

    to_vector = lambda color: Vector((color.h, color.s, color.v))

    vectors = [ (to_vector(c.color), c) for c in colors ]
    vector = to_vector(key)

    def create_new():
        color = palette.colors.new()
        color.name = name
        color.color = key
        color.color.s = key.s
        color.color.v = key.v
        color.color.h = key.h
        color.alpha = 1.0
        return color

    current = [color for (v, color) in vectors if  (v - vector).length < 1e-6 ]
    result = next(iter(current), False) or create_new()
    return result 



def freestyle_to_gpencil_strokes(strokes, frame, lineset, options): # draw_mode='3DSPACE', color_extraction='BASE'):
    mat = bpy.context.scene.camera.matrix_local.copy()

    # pick the active palette or create a default one
    grease_pencil = bpy.context.scene.grease_pencil
    palette = grease_pencil.palettes.active or grease_pencil.palettes.new("GP_Palette")

    # can we tag the colors the script adds, to remove them when they are not used? 
    cache = { color_to_hex(color.color) : color for color in palette.colors } 


    # keep track of which colors are used (to remove unused ones)
    used = []

    for fstroke in strokes:

        if options.color_extraction:
            if options.color_extraction_mode == 'FIRST':
                base_color = fstroke[0].attribute.color
            elif options.color_extraction_mode == 'FINAL':
                base_color = fstroke[-1].attribute.color
            else:
                base_color = lineset.linestyle.color



        # color has to be frozen (immutable) for it to be stored
        base_color.freeze()

        colorname = get_colorname(palette.colors, base_color, palette).name

        # append the current color, so it is kept
        used.append(colorname)

        gpstroke = frame.strokes.new(colorname=colorname)
        gpstroke.draw_mode = options.draw_mode
        gpstroke.points.add(count=len(fstroke), pressure=1, strength=1)

        # the max width gets pressure 1.0. Smaller widths get a pressure 0 <= x < 1 
        base_width = functools.reduce(max, (sum(svert.attribute.thickness) for svert in fstroke), lineset.linestyle.thickness)

        # set the default (pressure == 1) width for the gpstroke
        gpstroke.line_width = base_width

        if options.draw_mode == '3DSPACE':
            for svert, point in zip (fstroke, gpstroke.points):
                point.co = mat * svert.point_3d
                # print(point.co, svert.point_3d)

                if options.thickness_extraction:
                    point.pressure = sum(svert.attribute.thickness) / max(1e-6, base_width)

                if options.alpha_extraction:
                    point.strength = svert.attribute.alpha

        elif options.draw_mode == 'SCREEN':
            width, height = render_dimensions(bpy.context.scene)
            for svert, point in zip (fstroke, gpstroke.points):
                x, y = svert.point
                point.co = Vector((abs(x / width), abs(y / height), 0.0)) * 100

                if options.thickness_extraction:
                    point.pressure = sum(svert.attribute.thickness) / max(1e-6, base_width)

                if options.alpha_extraction:
                    point.strength = svert.attribute.alpha

        else:
            raise NotImplementedError()


def freestyle_to_strokes(scene, lineset, strokes):
    default = dict(color=(0, 0, 0), alpha=1, fill_color=(0, 1, 0), fill_alpha=0)

    # name = "FS {} f{:06}".format(lineset.name, scene.frame_current)
    name = "FS {}".format(lineset.name)
    layer, frame = create_gpencil_layer(scene, name, **default)
    # render the normal strokes 
    #strokes = render_visible_strokes()

    exporter = scene.freestyle_gpencil_export
    linestyle = lineset.linestyle


    options = DrawOptions(draw_mode= exporter.draw_mode
            , color_extraction = linestyle.use_extract_color
            , color_extraction_mode = linestyle.extract_color
            , alpha_extraction = linestyle.use_extract_alpha
            , thickness_extraction = linestyle.use_extract_thickness
            )
    freestyle_to_gpencil_strokes(strokes, frame, lineset, options)


classes = (
    FreestyleGPencil,
    SVGExporterPanel,
    FSGPExporterLinesetPanel,
    )




class StrokeCollector(StrokeShader):
    def __init__(self):
        StrokeShader.__init__(self)
        self.viewmap = []

    def shade(self, stroke):
        self.viewmap.append(stroke)

class Callbacks:
    @classmethod
    def poll(cls, scene, linestyle):
        return scene.render.use_freestyle and scene.freestyle_gpencil_export.use_freestyle_gpencil_export

    @classmethod
    def modifier_post(cls, scene, layer, lineset):
        if not cls.poll(scene, lineset.linestyle):
            return []

        cls.shader = StrokeCollector()
        return [cls.shader]

    @classmethod
    def lineset_post(cls, scene, layer, lineset):
        if not cls.poll(scene, lineset.linestyle):
            return []

        strokes = cls.shader.viewmap
        freestyle_to_strokes(scene, lineset, strokes)





def register():
    linestyle = bpy.types.FreestyleLineStyle

    linestyle.use_extract_color = BoolProperty(
            name="Extract Stroke Color",
            description="Apply Freestyle stroke color to Grease Pencil strokes",
            default=True,
            )
    linestyle.use_extract_fill = BoolProperty(
            name="Extract Fill Color",
            description="Apply Material color to Grease Pencil fills",
            default=False,
            )
    linestyle.use_extract_thickness = BoolProperty(
            name="Extract Thickness",
            description="Apply Freestyle thickness values to Grease Pencil strokes",
            default=False,
            )
    linestyle.use_extract_alpha = BoolProperty(
            name="Extract Alpha",
            description="Apply Freestyle alpha values to Grease Pencil strokes",
            default=False,
            )

    linestyle.extract_color= EnumProperty(
            name="Stroke Color Mode",
            items=(
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

    parameter_editor.callbacks_modifiers_post.append(Callbacks.modifier_post)
    parameter_editor.callbacks_lineset_post.append(Callbacks.lineset_post)

def unregister():

    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.freestyle_gpencil_export
    del bpy.types.GPencilPaletteColor.fsgpexporter

    del bpy.types.FreestyleLineStyle.use_extract_color
    del bpy.types.FreestyleLineStyle.use_extract_fill
    del bpy.types.FreestyleLineStyle.use_extract_thickness
    del bpy.types.FreestyleLineStyle.use_extract_alpha
    del bpy.types.FreestyleLineStyle.extract_color

    del bpy.types.GPencilLayer.frame


    parameter_editor.callbacks_modifiers_post.remove(Callbacks.modifier_post)
    parameter_editor.callbacks_lineset_post.remove(Callbacks.lineset_post)

if __name__ == '__main__':
    register()

