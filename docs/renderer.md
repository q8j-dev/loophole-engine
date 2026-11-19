# How the renderer works

Scratch has no 3D. TurboWarp's Pen+ extension adds custom shaders, render targets and triangle lists drawn from Scratch lists, and Loophole builds a deferred-style renderer on top of those. The expensive work happens once, at build time, in Python. The game in TurboWarp only looks results up.

## At build time

### Levels become voxels, then rectangles

`world.py` describes boxes: rooms carved out of rock, solids filled back in, platforms, stairs and buildings. The builder rasterizes them into a 0.5 m voxel grid (`loophole/level.py`), finds every face between air and solid, and merges neighbouring faces with the same material into large rectangles. The rectangles are the collision geometry, the lightmap charts and the mesh.

Outdoor levels voxelize only what you placed and leave every boundary open. Terrain is a separate heightfield mesh (`loophole/terrain.py`) with a low-resolution ring that runs out to the horizon.

`loophole/kit.py` then adds detail the voxels can't express: skirting and lips at floor-wall seams, beams, window frames, sign lettering and hazard stripes. `loophole/buildings.py` adds roofs, fascia, sills, glass and plinths to buildings.

### Lighting is baked

`loophole/bake.py` computes the lighting with Monte Carlo ray tracing against the voxel grid:

1. Direct light from every point, spot, strip and panel light, with soft shadows from jittered samples on the light's area. Outdoor levels add the sun with a soft penumbra and sky light from rays that escape.
2. Indirect light. Each lightmap texel gathers bounced light from the already-lit surfaces, 128 rays at the default bake quality.
3. A directional lightmap. Each texel stores irradiance plus a dominant light direction, so normal maps still respond to baked light.
4. An ambient probe grid that lights moving objects, the held item and the player.
5. Vertex lighting for props, with leaves offset so canopies don't go black.
6. A terrain lightmap at 0.5 m that combines sun visibility, found by marching the heightfield, with sky visibility and light filtered through tree crowns.

Results are cached under `.loophole/cache`, keyed by a hash of the level contents and prop meshes. Rebuilding without changing the level takes about five seconds.

### Geometry is packed into images

Pen+ draws triangles from Scratch lists, and lists of hundreds of thousands of numbers load slowly. Loophole stores every vertex as 8 RGB texels in a PNG instead: position at 16-bit precision, normal, lightmap coordinate, material, ambient occlusion, a seed, a bone index, a flag and a tangent. The vertex shader reads the texels for each vertex index (vertex pulling), so one short index list draws any mesh.

### Textures are packed per game

Pen+ textures have no mipmaps, so every atlas cell stores its own mip chain and the shader picks and blends levels itself. At build time `loophole/texpack.py` reads the world shader's material table to work out which material cells the game uses, copies only those, and drops the top mip level unless `textures="high"`. Props are packed the same way into a per-game decor atlas (`loophole/decor_pack.py`). The showcase went from 63 MB to 23 MB this way.

### Gameplay scripts are compiled

`loophole/runtime/engine.py` is the engine itself, written in a subset of Python. `loophole/sbc.py` compiles it into Scratch blocks. Your `game.py` goes through the same compiler.

## Every frame in TurboWarp

1. **Simulation.** Movement, collision against the merged rectangles, objects, paths, buttons, doors and triggers. Broadcasts go out to your scripts here.
2. **Camera.** First person, free, a third-person orbit with wall clipping, or a top-down orbit with an optional cutaway plane.
3. **G-buffer.** Depth and normals go to a render target that TAA, screen-space reflections and haze use.
4. **Sky.** A gradient sky with a sun disc and drifting clouds. Skipped indoors.
5. **Main pass.** One world shader shades every surface:
   - baked irradiance from the directional lightmap,
   - up to 24 dynamic lights with GGX specular,
   - reflections from a parallax-corrected environment probe, refined by screen-space ray marching on glossy floors,
   - soft shadows from up to four moving objects and the player's capsule,
   - per-pixel height fog, alpha-tested foliage with wind sway and translucency, and the rim highlight on pickups.
6. **Grass and particles.** Camera-following grass cards on terrain, and dust in indoor light shafts.
7. **Held item.** The viewmodel draws last with a compressed depth range so it never clips into walls.
8. **Volumetric haze.** A pass marches 24 steps along each pixel's view ray and adds in-scattered light from up to 8 lights marked with `haze`. It is then blurred.
9. **Temporal anti-aliasing.** The camera jitters by a sub-pixel offset each frame. The resolve reprojects the previous frame with the depth buffer and clamps it to the current pixel's neighbourhood to avoid ghosting.
10. **Bloom and exposure.** A bright pass is blurred at two radii. A one-pixel render target holds the log-average scene brightness and adapts over time, which drives auto exposure.
11. **Composite.** Exposure, ACES tone mapping, the colour grade, fades and flashes.
12. **HUD.** The `message` and `status` text draws as glyph quads from a font atlas. The layout updates only when the text changes.

## Characters

Imported characters (`loophole/character.py`) use rigid skinning. Each vertex follows the joint with the largest weight. At build time the importer samples the idle, walk, run and jump clips at 15 frames per second into joint matrices. Each frame the engine interpolates between the two nearest frames, eases toward the target pose (which also crossfades when the clip changes), and uploads the matrices to a uniform array that the vertex shader indexes by each vertex's bone.

## Performance

In the playtest harness on an M-series MacBook at 720p, the lab, valley and orchard run at about 60 frames per second. The crypt vault, with its many flickering lights, drops to about 35 at 1080p. `Game(quality=1)` renders at a lower internal resolution for slower machines. Bake time scales with level size: 4 seconds for the starter and about 35 seconds for the showcase valley.
