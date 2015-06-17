Freestyle to GPencil 
====================

<p align="center"><img src ="https://rawgit.com/folkertdev/freestyle-gpencil-exporter/master/images/header.png" /></p>

A tool for converting the Freestyle view map (i.e. Freestyle strokes) to Grease Pencil strokes. This may be useful for inspecting how Freestyle lines are generated, or to further manipulate Freestyle strokes with Blender's excellent (and recently improved) GPencil tools. 


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
 
