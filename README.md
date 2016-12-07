Freestyle to GPencil 
====================


<p align="center"><img src ="https://rawgit.com/folkertdev/freestyle-gpencil-exporter/development/images/header.png" /></p>

A tool for converting Freestyle strokes to Grease Pencil strokes.  

## Features 

With the latest version, it is possible to extract styling from Freestyle strokes. 

### Render options
<img src ="https://rawgit.com/folkertdev/freestyle-gpencil-exporter/development/images/render_menu.png" align="right" /> 

* **Draw mode** Draw mode for the Grease Pencil strokes
* **Write mode** Keep adds newly generated strokes to the active GPencil layer. Overwrite first clears the 
    active GPencil later and then adds the newly generated strokes

### Lineset options

<img src ="https://rawgit.com/folkertdev/freestyle-gpencil-exporter/development/images/lineset_menu.png" align="right" /> 

* **Extract Color** There are three possibilities for color extraction
    - Linestyle base color 
    - First vertex of the Freestyle stroke
    - Final vertex of the Freestyle stroke
* **Extract Thickness** Transfers thickness from every Freestyle vertex to every GPencil vertex
* **Extract Alpha** Transfers alpha from every Freestyle vertex to every GPencil vertex

The geometry is always extracted, but may give unexpected results in **3D Space** mode. The geometry modifiers 
work on the screen (so 2D) coordinates, so their effects are not representable in **3D Space** mode.

<p align="center">
<img src ="https://rawgit.com/folkertdev/freestyle-gpencil-exporter/development/images/geometry_modifier_screen_mode.png" 
/> 
<img src ="https://rawgit.com/folkertdev/freestyle-gpencil-exporter/development/images/geometry_modifier_3dspace_mode.png"  /> 
<br>
<label style="margin-left:auto;margin-right:auto; width:100%">A geometry modifier in Screen (left) and 3D Space (right) mode</label>
</p>



## GPencil to Curve


Conversion from GPencil to a curve object is possible, but generates an unexpected result by default. This is because GPencil -> Curve doesn't respect splines (all points are put in one spline), so there are extra curve segments connecting what should be lose stroke segments. 

Luckily, there is a simple option to turn this off:
<p>
<img src ="https://rawgit.com/folkertdev/freestyle-gpencil-exporter/master/images/export_as_curve.png"  align="right"/>
The <span>Link Strokes<span> setting (bottom row on the image) makes the extra segments go away.
The result is a curve exactly resembling the Freestyle output. This has millions of opportunities, like creating the curve once (with Freestyle -> GPencil -> Curve) and then rendering the curve instead of Freestyle, adding particle systems (seemingly) on Freestyle strokes, exporting to other programs/formats and using all kinds of modifiers (curve, explode).
 </p>

<br>
<br>
<br>
<br>
<br>
<br>


Installing 
========== 

This addon can be installed like any other: 

* Download the file (or clone the whole repository)
* Open Blender
* Open User Preferences (File > User Preferences)
* Press Install from File... (bottom row), navigate to the addon file and press enter 
* Enable the addon
* The addon should now be installed and running (Properties > Render)
* Don't forget to save the user preferences if you want the addon to stay enabled 
 
