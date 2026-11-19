# Credits

All third-party art in Loophole Engine is CC0 1.0 (public domain) or under the SIL Open Font License. Everything else was made for this project and is MIT licensed with the code.

## Material textures

`loophole/data/atlas/materials.jpg`:

- ambientCG: Plastic013A, MetalPlates006, Metal032, DiamondPlate008C
- Poly Haven: metal_plate_02, concrete_floor_worn_001, concrete_tile_facade, rusty_metal_02, metal_grate_rusty, painted_metal_shutter, smooth_concrete_floor

`loophole/data/atlas/materials2.jpg` and `materials3.jpg`, all from Poly Haven:

leafy_grass, dark_rock, coast_sand_01, brown_mud_dry, brick_wall_001, old_wood_floor, brown_planks_05, painted_plaster_wall, floor_tiles_06, castle_brick_07, cobblestone_floor_08, bark_brown_02, asphalt_02, snow_02, cliff_side, gravel_road, clay_roof_tiles_02, marble_01

## Prop models

These Poly Haven models were decimated, unwrapped and baked into the prop library by `tools/build_props.py`:

ArmChair_01, Barrel_01, boulder_01, brass_goblets, Chandelier_01, ClassicNightstand_01, concrete_cat_statue, food_apple_01, GothicBed_01, gothic_statue, hanging_picture_frame_01, industrial_wall_lamp, industrial_wall_sconce, Lantern_01, namaqualand_boulder_02, painted_wooden_bench, painted_wooden_cabinet, Sofa_01, stone_fire_pit, street_lamp_01, street_rat, tool_cart, treasure_chest, tree_stump_01, vintage_oil_lamp, wine_barrel_01, wooden_bookshelf_worn, wooden_bucket_01, wooden_candlestick, wooden_crate_01, WoodenChair_01, WoodenTable_01, dead_tree_trunk, rock_moss_set_01

## Characters

The knight, mage, rogue and barbarian player characters come from the KayKit Character Pack: Adventurers by Kay Lousberg (kaylousberg.com), CC0 1.0. `tools/make_characters.py` converts them with their Idle, Walking_A, Running_A and Jump_Idle animations.

## Foliage

`tools/make_foliage.py` builds the trees, bushes, grass and ferns from these Poly Haven textures: island_tree_01 leaves, jacaranda_tree leaves (willow fronds), pine_tree_01 twigs and bark, fir_sapling twigs, grass_medium_01, fern_02, bark_brown_02.

## Fonts

- HUD text: Rubik by the Rubik Project Authors, SIL Open Font License 1.1 (`licenses/OFL-Rubik.txt`). Rendered into `loophole/data/font.png` by `tools/make_font.py`.
- Sign lettering: Barlow Condensed by the Barlow Project Authors, SIL Open Font License 1.1 (`licenses/OFL-BarlowCondensed.txt`). Converted to outlines in `loophole/data/glyphs.npz` by `tools/make_glyphs.py`.

## Made for this project

The lab kit props, the cube, door, button, device, arms and player models, and the sound pack in `loophole/data/sfx` (synthesized by `tools/sfx.py`).
