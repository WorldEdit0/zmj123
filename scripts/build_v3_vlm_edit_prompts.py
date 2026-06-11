#!/usr/bin/env python3
"""Build hand-authored edit prompts for source_videos_v3 using VLM metadata."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/edit_prompts_v3_vlm"
SOURCE_JSON = ROOT / "source_prompts_multishot_v3_cn_flexible_draft.json"
VLM_DIR = ROOT / "runs/pilot_v3/vlm_reannotation"
SHOT_DIR = ROOT / "data/source_videos_v3_unpacked/home/tiger/pilot_v3/shots"
AUTHOR = "codex-handwritten-v3-vlm-boundaryfix-20260611"


SHOT_BRIEFS = {
    "00000": [
        "The barista extracts dark coffee into the white cup beside the black espresso machine.",
        "The barista pours steamed milk from the silver pitcher into the cup on the saucer.",
        "The overhead close-up shows the leaf-shaped latte art forming in the cup.",
        "The finished latte is wiped, turned, and slid forward while cafe customers sit behind it.",
    ],
    "00001": [
        "The dog and trainer are established on the grass agility course with obstacles ahead.",
        "The Border Collie jumps over the blue bar and lands toward the tunnel.",
        "The dog enters the yellow tunnel and races out toward the seesaw.",
        "The dog sits before the trainer and receives the reward treat.",
    ],
    "00002": [
        "The red toy train starts from the striped block station on the wooden floor.",
        "The train crosses the blue arch bridge while the green wind-up robot passes behind it.",
        "The train circles the plaza with lamps and stops at the second station.",
    ],
    "00003": [
        "The school robot club room is established with the girl, boy, desktop robot, and hallway students.",
        "Hands tighten a screw in the transparent robot shell with a small screwdriver.",
        "The wheeled robot follows the table line and raises its red flag.",
        "The girl celebrates while the boy claps and the robot spins on the table.",
    ],
    "00004": [
        "The sunflower seedling emerges from dark moist soil with water droplets glistening.",
        "The seedling is misted in its terracotta pot while a bee circles nearby.",
        "The overhead pot view shows four green leaves and a central bud as sunlight moves across them.",
    ],
    "00005": [
        "Two paramedics prepare the folded stretcher beside the ambulance at the hospital entrance.",
        "The male paramedic checks and locks the stretcher wheel assembly.",
        "Medical supplies, the oxygen mask, gauze, and scissors are checked in the open kit.",
        "The paramedics unfold and align the stretcher under the ambulance lights.",
        "The stretcher is rolled toward the hospital doors while the nurse passes with a medical cart.",
    ],
    "00006": [
        "The squirrel catches an acorn near the tree hollow and basket.",
        "The gray raccoon washes red berries in the blue stream.",
        "The spotted fawn lowers its head to smell the white wildflower.",
        "The forest animals gather around the flower and wave together.",
    ],
    "00007": [
        "The engineer launches the black quadcopter from the yellow landing pad near the bridge.",
        "The drone flies close to the bridge cables and inspection surfaces.",
        "The drone camera inspects the rusted crack on the bridge girder above the river.",
        "The engineer reads the tablet heat-map interface with the crack marker.",
        "The drone returns toward the landing pad as the large boat moves under the bridge.",
    ],
    "00008": [
        "The white delivery robot leaves the fruit stall with the brown paper package.",
        "The robot scans the QR code on the cobblestone path while the cleaning robot sits in the background.",
        "The robot passes crates of tomatoes and market shoppers under striped awnings.",
        "The robot hands the paper package through the wooden pickup window.",
    ],
    "00009": [
        "The street painter works at the easel in the plaza with pigeons and distant pedestrians.",
        "The painter adds watercolor detail near the fountain while pigeons move on the cobblestones.",
        "The painter presents the finished plaza painting against the classical building backdrop.",
    ],
    "00010": [
        "The orange-and-white cat peeks from under bakery furniture near flour paw prints.",
        "The cat sniffs the paper bag holding the baguette beside the glass display case.",
        "The cat presses a fresh flour paw print onto the wooden surface.",
        "The cat rests near the baguette and croissant as the passerby moves outside the glass door.",
    ],
    "00011": [
        "The clay astronaut stands by the cardboard rocket, red button, blue wrench, and green alien ball.",
        "The astronaut tapes the crack on the cardboard rocket with silver tape.",
        "The astronaut tightens the rocket nut with the bright blue wrench.",
        "The astronaut presses the red launch button and white smoke appears.",
        "The repaired rocket glows and smokes while the green alien watches.",
    ],
    "00012": [
        "Night commuters with umbrellas move through the wet neon transit entrance.",
        "A yellow-jacket delivery scooter passes the bus stop as passengers move around the bus.",
        "Rain falls across taxis, umbrellas, and glowing billboards in the intersection.",
        "Pedestrians with colorful umbrellas cross the reflective night street.",
    ],
    "00013": [
        "The chef sets up the white plate on the stainless pass and raises the piping bag.",
        "The nozzle pipes three ivory cream domes into a triangle on the white plate.",
        "The chef dots deep red raspberry sauce between the cream domes.",
        "The chef places the mint leaf, rings the silver service bell, and inspects the dessert.",
    ],
    "00014": [
        "The golden-red koi swims under lotus leaves near the stone bridge and lantern.",
        "The blue dragonfly hovers by the bamboo water spout as ripples spread across the pond.",
        "The koi circles under petals, lotus stems, and mossy rocks in the overhead view.",
    ],
    "00015": [
        "The red classic car is established in the garage with mechanics and tool shelves.",
        "A mechanic polishes the chrome side mirror with a cloth.",
        "The wrench tightens a bolt inside the engine bay.",
        "The whitewall tire and chrome hubcap are shown in detail.",
        "The restored car gleams under the work lights as the mechanic checks the finish.",
    ],
    "00016": [
        "The floating island with the glowing blue tree hangs over purple cloud seas.",
        "Large blue crystals and glowing flowers surround the tree roots.",
        "Waterfalls fall from the island edge into the cloud layer.",
        "The hollow glowing tree releases white sparks among tall grass leaves.",
    ],
    "00017": [
        "The bride stands on the pedestal before mirrors while the seamstress and flower girl are visible.",
        "The seamstress adjusts the ivory lace dress and button closure.",
        "Hands arrange the veil and silver beaded headpiece.",
        "The bride and seamstress inspect the finished fit in the three-panel mirror.",
    ],
    "00018": [
        "The yellow wind-up duck and blue tin car line up on the toy racetrack.",
        "The duck and car race between colorful blocks under sunlight.",
        "The duck wins by the finish flags as cartoon stars appear above it.",
    ],
    "00019": [
        "The horse and rider approach the green-marked jump inside the sand arena.",
        "The chestnut horse takes off over the white rails with the rider balanced above it.",
        "The horse lands and kicks up sand particles.",
        "The rider guides the horse away while the staff member and pony pass in the background.",
    ],
    "00020": [
        "Museum visitors circle the marble sculpture under the skylight in the exhibition hall.",
        "A visitor in a brown coat walks past the bronze mask inside the glass display case.",
    ],
    "00021": [
        "Waves crash over black reef rocks below the white lighthouse.",
        "Orange-brown seaweed and a tide pool reflect the lighthouse.",
        "The small fishing boat sits near the horizon beyond the rocks and water.",
        "The lighthouse beam sweeps across shells, wet sand, and the evening sea.",
    ],
    "00022": [
        "The rover approaches the target rock across red sand with a dust devil in the distance.",
        "The rover wheels and blue solar panel pass a yellow warning marker.",
        "The rover extends its mechanical arm toward the target rock under the orbiter point.",
        "The drill cuts into the dark rock and throws red-brown powder.",
        "The spherical rock sample is sealed into the transparent sample tube.",
        "The rover departs over its tracks while the dust devil remains on the horizon.",
    ],
    "00023": [
        "The dancer rehearses in the mirrored studio with the barre, windows, and reflected dancers.",
        "The dancer pauses near the blue water bottle at the mirror wall.",
        "A close-up shows the pink ballet shoes working on the marked wooden floor.",
        "The dancer repeats the phrase while the mirror doubles the movement.",
        "The dancer finishes the rehearsal sequence in the window light.",
    ],
    "00024": [
        "The ramen apprentice and older chef are established behind the wooden counter.",
        "The apprentice lifts noodles from the metal pot with chopsticks and bamboo strainer.",
        "The ramen bowl is topped with chashu, scallions, and soft-boiled egg beside the lucky cat.",
        "The apprentice presents the completed bowl while the older chef supervises.",
    ],
    "00025": [
        "The white egret steps through shallow wetland water near reeds and the boardwalk.",
        "The blue-green and orange kingfisher perches on a dead branch.",
        "Three brown ducks swim through water framed by foreground leafy plants.",
    ],
    "00026": [
        "The red clay teapot with googly eyes puffs white flour on the wooden table.",
        "The wooden spoon lifts the brown sugar cube into the glossy blue bowl.",
    ],
    "00027": [
        "The bicycle mechanic checks the black road bike on the blue repair stand as the cyclist passes outside.",
        "Chain lube is applied to the silver chain and cassette cogs.",
        "The torque wrench tightens the rear derailleur bolt.",
        "The mechanic pedals the bike to test the chain shift while the red cyclist passes again.",
    ],
    "00028": [
        "The gardener and small white gardening robot work among rooftop tomato planters while the drone passes.",
        "The robot scans the tomato leaves with its extendable arm.",
        "The gardener adjusts the spray while the robot backs away from the water mist.",
        "The robot moves along the planter grid as the gardener supports the bamboo stakes.",
        "The gardener places harvested tomatoes into the wicker basket as the drone crosses the sky.",
    ],
    "00029": [
        "The blue alien traveler rolls the round suitcase through the spaceport under the boarding screen.",
        "The green three-eyed alien opens a backpack at the luggage belt as star stickers fly out.",
        "The maintenance robot welds the underside of the round spacecraft.",
        "Multicolored alien travelers sit in colorful seats under the space windows.",
        "A robot arm taps the boarding screen while alien travelers wait near the gate.",
        "The round spacecraft lifts from the glowing runway with blue exhaust flames.",
    ],
}


T1_DYNAMIC = [
    ("00000", "C1", "barista in white shirt and black apron", "elderly woman barista with silver hair, white shirt, and black apron", [1, 2, 3, 4], "Replace the barista with an elderly woman barista with short silver hair, while keeping the white shirt, black apron, latte-art motions, and cup interactions consistent."),
    ("00001", "A1", "black-and-white Border Collie", "golden retriever with a red collar", [1, 2, 3, 4], "Replace the black-and-white Border Collie with a golden retriever wearing a red collar, preserving every jump, tunnel run, seesaw finish, and reward reaction."),
    ("00002", "B1", "small green wind-up robot with yellow eyes", "small brass toy soldier marching behind the train", [1, 2], "Replace the small green wind-up robot with a small brass toy soldier marching behind the train in the toy city shots where it appears."),
    ("00003", "B1", "two hallway students in dark blue uniforms", "two elderly school janitors pushing a cleaning cart", [1], "Replace the two hallway students with two elderly school janitors pushing a cleaning cart, keeping them as distant background passersby."),
    ("00004", "B1", "small black bee", "small orange butterfly", [2], "Replace the small black bee with a small orange butterfly circling the sunflower seedling in the watering shot."),
    ("00005", "B1", "nurse in white uniform pushing a medical cart", "hospital security guard pushing the same medical cart", [1, 5], "Replace the white-uniformed nurse with a hospital security guard pushing the same medical cart in the background."),
    ("00006", "A2", "chubby gray raccoon with black facial markings", "round brown beaver with a flat tail", [2, 4], "Replace the gray raccoon with a round brown beaver with a flat tail, preserving the berry-washing action and the final group pose."),
    ("00007", "B1", "large white commercial boat on the river", "long red cargo barge on the river", [3, 5], "Replace the large white boat with a long red cargo barge moving below the bridge, leaving the drone inspection unchanged."),
    ("00008", "A1", "orange cat in the market", "small black-and-white market dog", [1, 4], "Replace the orange cat with a small black-and-white market dog, keeping it as a background animal near the delivery route."),
    ("00009", "A1", "gray-black pigeon group", "small group of white doves", [1, 2], "Replace the gray-black pigeons with a small group of white doves around the street painter."),
    ("00010", "B1", "person in pink shirt outside the bakery", "street musician carrying a violin case outside the bakery", [1, 4], "Replace the passerby outside the bakery with a street musician carrying a violin case, keeping the figure outside the glass door."),
    ("00011", "G1", "small green spherical alien with googly eyes", "tiny silver rolling repair robot", [1, 5], "Replace the small green alien ball with a tiny silver rolling repair robot beside the clay rocket setup."),
    ("00012", "B1", "food-delivery scooter rider in bright yellow jacket", "food-delivery cyclist in an orange rain poncho", [2], "Replace the yellow-jacket scooter rider with a food-delivery cyclist in an orange rain poncho in the bus-stop shot."),
    ("00013", "C1", "head chef in white uniform", "female pastry chef with a black headscarf and white uniform", [1, 2, 3, 4], "Replace the head chef with a female pastry chef wearing a black headscarf and white uniform, preserving all dessert-plating hand motions."),
    ("00014", "A2", "blue dragonfly with transparent wings", "small hummingbird with iridescent wings", [2], "Replace the blue dragonfly with a small hummingbird hovering beside the bamboo water spout."),
    ("00015", "C2", "second mechanic wearing gray clothing", "young apprentice mechanic in a navy hoodie", [1], "Replace the second mechanic with a young apprentice mechanic in a navy hoodie in the garage establishing shot."),
    ("00016", "VFX1", "white sparks released by the hollow glowing tree", "swarm of tiny golden fireflies", [4], "Replace the white sparks released by the hollow glowing tree with a swarm of tiny golden fireflies, preserving the magical release action."),
    ("00017", "B1", "young flower girl in white dress with pink basket", "young page boy in a cream suit carrying the same pink basket", [1], "Replace the flower girl with a young page boy in a cream suit carrying the same light pink basket."),
    ("00018", "T2", "blue tin toy car with expressive eyes", "green tin toy tractor with expressive eyes", [1, 2, 3], "Replace the blue tin toy car with a green tin toy tractor, preserving the race timing against the wind-up duck."),
    ("00019", "B1", "staff member leading a brown and white pony", "staff member leading a small gray donkey", [1, 4], "Replace the background pony with a small gray donkey led by the same staff member around the arena edge."),
    ("00020", "B1", "visitor in brown coat and red scarf", "museum photographer with a camera vest", [2], "Replace the visitor in the brown coat and red scarf with a museum photographer wearing a camera vest near the bronze mask case."),
    ("00021", "B1", "flock of seagulls and small white boat", "flock of dark cormorants and a small blue boat", [1, 3, 4], "Replace the seagulls and small white boat with dark cormorants and a small blue boat across the coastline montage."),
    ("00022", "B2", "bright orbiter point in the sky", "small meteor streak crossing the sky", [3], "Replace the bright orbiter point with a small meteor streak crossing the sky in the rover arm shot."),
    ("00023", "B1", "two reflected dancers in dark blue leotards", "two reflected male tap dancers in black suits", [1, 2, 4, 5], "Replace the two reflected background dancers with two reflected male tap dancers in black suits while keeping them in the mirrors."),
    ("00024", "C2", "gray-haired older ramen master in gray traditional clothing", "elderly woman ramen master in a cream kimono jacket", [1, 4], "Replace the older ramen master with an elderly woman ramen master in a cream kimono jacket, preserving her supervisory role."),
    ("00025", "A3", "three brown ducks", "three black-and-white coots", [2, 3], "Replace the three brown ducks with three black-and-white coots swimming through the wetland water."),
    ("00026", "B1", "red cherry tomato", "small yellow lemon", [1, 2], "Replace the rolling red cherry tomato with a small yellow lemon in both clay kitchen shots."),
    ("00027", "B1", "cyclist in red clothing outside the workshop", "skateboard courier passing outside the workshop", [1, 4], "Replace the red-clothed cyclist outside the window with a skateboard courier passing outside the workshop."),
    ("00028", "B1", "black delivery drone in the rooftop sky", "small blue delivery blimp", [1, 5], "Replace the black delivery drone with a small blue delivery blimp in the rooftop sky."),
    ("00029", "R2", "white round cleaning robot with blue eyes", "small floating luggage drone", [2], "Replace the wall-mounted white cleaning robot with a small floating luggage drone in the luggage-belt shot."),
]


T1_STATIC = [
    ("00000", "white ceramic latte cup", "shallow white ceramic latte bowl", [1, 2, 3, 4], "Replace the white ceramic latte cup with a shallow white ceramic latte bowl that can still receive the espresso and milk pour."),
    ("00001", "blue jump bar", "low rope hurdle", [1, 2, 3], "Replace the blue jump bar with a low rope hurdle that the dog can still clear during the agility run."),
    ("00002", "green train carriage", "small wooden cargo wagon", [2, 3], "Replace the green train carriage with a small wooden cargo wagon while keeping it coupled behind the red toy train."),
    ("00003", "small red flag on the robot", "tiny blinking signal beacon on the robot", [3, 4], "Replace the robot's small red flag with a tiny blinking signal beacon after the table-line run."),
    ("00004", "terracotta orange pot", "small rectangular wooden planter box", [2, 3], "Replace the terracotta pot with a small rectangular wooden planter box in the wider sunflower shots."),
    ("00005", "blue stretcher mattress", "orange rescue backboard", [1, 2, 4, 5], "Replace the blue stretcher mattress with an orange rescue backboard while preserving the stretcher support function."),
    ("00006", "acorn basket", "small canvas foraging satchel", [1, 4], "Replace the squirrel's acorn basket with a small canvas foraging satchel in the forest montage."),
    ("00007", "yellow drone landing pad", "folding metal drone docking stand", [1, 5], "Replace the yellow drone landing pad with a folding metal drone docking stand at the bridgehead."),
    ("00008", "brown paper package", "white insulated delivery cooler", [1, 4], "Replace the brown paper package with a white insulated delivery cooler while preserving the delivery handoff."),
    ("00009", "wooden easel", "portable tripod display stand", [1, 2, 3], "Replace the wooden easel with a portable tripod display stand throughout the street-painting scene."),
    ("00010", "brown paper bag holding the baguette", "small wicker bread basket", [1, 2, 4], "Replace the brown paper baguette bag with a small wicker bread basket near the bakery cat."),
    ("00011", "blue plastic wrench", "yellow toy screwdriver", [1, 3], "Replace the bright blue wrench with a yellow toy screwdriver in the clay astronaut repair shots."),
    ("00012", "dark umbrellas", "clear plastic rain ponchos", [1, 4], "Replace the commuters' dark umbrellas with clear plastic rain ponchos in the rainy transit montage."),
    ("00013", "dark purple squeeze bottle", "glass sauce dropper pipette", [3], "Replace the dark purple squeeze bottle with a glass sauce dropper pipette for placing the sauce dots."),
    ("00014", "traditional gray stone lantern", "small wooden torii marker", [1, 3], "Replace the gray stone lantern with a small wooden torii marker at the koi pond edge."),
    ("00015", "chrome side mirror", "chrome hood ornament", [2], "Replace the car's chrome side mirror with a chrome hood ornament during the polishing close-up."),
    ("00016", "transparent blue crystal stones", "cluster of glowing blue mushrooms", [2], "Replace the blue crystal stones around the glowing tree roots with a cluster of glowing blue mushrooms."),
    ("00017", "silver beaded headpiece", "fresh white floral crown", [3, 4], "Replace the bride's silver beaded headpiece with a fresh white floral crown while keeping the veil attached."),
    ("00018", "red finish flags", "small striped finish arch", [1, 3], "Replace the red finish flags with a small striped finish arch on the toy racetrack."),
    ("00019", "white jump rails with green markers", "stacked hay-bale jump blocks", [1, 2, 3, 4], "Replace the white jump rails with stacked hay-bale jump blocks while keeping a jumpable obstacle in the arena."),
    ("00020", "black barrier ropes", "low glass safety barrier", [1], "Replace the black barrier ropes around the marble sculpture with a low glass safety barrier."),
    ("00021", "small white boat on the horizon", "red sea kayak on the horizon", [3], "Replace the small white fishing boat with a red sea kayak on the coastline horizon."),
    ("00022", "transparent glass sample tube", "sealed metal sample pod with a window", [5], "Replace the transparent sample tube with a sealed metal sample pod with a window."),
    ("00023", "blue plastic water bottle", "rolled white towel", [2], "Replace the blue water bottle by the mirror with a rolled white towel."),
    ("00024", "white ramen bowl with red rim", "black ceramic donburi pot", [1, 2, 3, 4], "Replace the white ramen bowl with a red rim with a black ceramic donburi pot that can still hold the ramen and toppings."),
    ("00025", "dead gray-brown branch", "thin bamboo perch", [2], "Replace the kingfisher's dead gray-brown branch with a thin bamboo perch."),
    ("00026", "glossy blue ceramic bowl", "shallow white mixing dish", [2], "Replace the glossy blue bowl with a shallow white mixing dish that can still receive the sugar cube."),
    ("00027", "white chain lube bottle", "small metal squeeze oil can", [2], "Replace the white chain lube bottle with a small metal squeeze oil can in the drivetrain close-up."),
    ("00028", "wicker tomato basket", "green plastic harvest crate", [5], "Replace the wicker tomato basket with a green plastic harvest crate in the rooftop harvest shot."),
    ("00029", "gray round suitcase", "floating transparent luggage pod", [1, 5], "Replace the gray round suitcase with a floating transparent luggage pod for the blue alien traveler."),
]


T2_SPECS = [
    ("00000", "C1", "plain black apron", "black apron with thin vertical pinstripes", "pattern", [1, 2, 3, 4]),
    ("00000", "O2", "smooth silver stainless steel milk pitcher", "brushed copper milk pitcher", "material_finish", [2, 3]),
    ("00001", "A1", "short black-and-white Border Collie fur", "slightly shaggy black-and-white Border Collie fur", "fur_length", [1, 2, 3, 4]),
    ("00001", "O1", "solid blue jump bar", "blue jump bar with white spiral tape markings", "pattern", [1, 2, 3]),
    ("00002", "T1", "glossy red toy train body", "matte red toy train body", "surface_finish", [1, 2, 3]),
    ("00002", "B1", "round yellow robot eyes", "square yellow robot eyes", "shape", [1, 2]),
    ("00003", "C1", "short dark schoolgirl bob haircut", "long twin-braid hairstyle", "hairstyle", [1, 4]),
    ("00003", "O1", "blue circuit board inside the transparent robot", "orange glowing circuit board inside the transparent robot", "light_color", [1, 2, 3, 4]),
    ("00004", "P1", "smooth vibrant green sunflower leaves", "veiny textured green sunflower leaves", "leaf_texture", [2, 3]),
    ("00004", "O1", "matte terracotta flower pot", "glossy terracotta flower pot", "surface_finish", [2, 3]),
    ("00005", "C1", "plain deep blue paramedic uniform", "deep blue paramedic uniform with reflective silver stripes", "reflective_pattern", [1, 3, 4, 5]),
    ("00005", "O2", "smooth blue stretcher mattress", "quilted blue stretcher mattress", "texture", [1, 2, 4, 5]),
    ("00006", "A1", "plain blue scarf on the squirrel", "blue scarf with tiny white dots", "pattern", [1, 4]),
    ("00006", "O6", "red berries", "bright purple berries", "color", [2, 4]),
    ("00007", "C1", "flat yellow safety vest", "mesh-textured yellow safety vest", "material_texture", [1, 4, 5]),
    ("00007", "M1", "steady red drone indicator lights", "blinking green drone indicator lights", "light_behavior", [1, 2, 3, 4, 5]),
    ("00008", "R1", "blue circular robot eyes", "blue crescent-shaped robot eyes", "shape", [1, 2, 3, 4]),
    ("00008", "O4", "red and white striped awning", "red and white checkerboard awning", "pattern", [1, 3]),
    ("00009", "C1", "smooth blue-green painter jacket", "corduroy blue-green painter jacket", "material_texture", [1, 2, 3]),
    ("00009", "O3", "multi-color watercolor palette", "pastel-only watercolor palette", "palette_color", [2, 3]),
    ("00010", "A1", "short orange-and-white cat fur", "long fluffy orange-and-white cat fur", "fur_length", [1, 2, 3, 4]),
    ("00010", "TXT1", "white 'Lattes & Croissants' storefront text", "gold 'Lattes & Croissants' storefront text", "text_color", [4]),
    ("00011", "T1", "smooth white clay astronaut suit", "ribbed white clay astronaut suit", "surface_texture", [1, 2, 3, 4, 5]),
    ("00011", "O6", "soft round cotton-like smoke", "thin spiral cotton-like smoke", "effect_shape", [4, 5]),
    ("00012", "B1", "bright yellow delivery jacket", "bright yellow delivery jacket with black sleeve stripes", "pattern", [2]),
    ("00012", "G1", "plain dark commuter umbrellas", "dark commuter umbrellas with silver rims", "trim_pattern", [1, 4]),
    ("00013", "C1", "smooth white chef uniform", "white chef uniform with double-breasted black buttons", "clothing_detail", [1, 2, 3, 4]),
    ("00013", "O6", "deep red raspberry sauce dots", "dark blackberry-purple sauce dots", "food_color", [3, 4]),
    ("00014", "A1", "golden-red koi scales", "golden-red koi scales with larger black-edged markings", "scale_pattern", [1, 2, 3]),
    ("00014", "O2", "rounded pink cherry blossom petals", "pointed pink cherry blossom petals", "shape", [1, 2, 3]),
    ("00015", "V1", "glossy red classic car paint", "matte red classic car paint", "surface_finish", [1, 2, 3, 4, 5]),
    ("00015", "O14", "whitewall tire stripe", "cream-colored tire stripe", "color", [4]),
    ("00016", "P1", "blue glowing tree leaves", "violet glowing tree leaves", "glow_color", [1, 2, 3, 4]),
    ("00016", "O6", "small multicolored glowing flowers", "larger bell-shaped multicolored glowing flowers", "flower_shape", [2, 4]),
    ("00017", "C2", "plain blue seamstress shirt", "blue seamstress shirt with small pearl buttons", "clothing_detail", [1, 2, 3, 4]),
    ("00017", "O1", "ivory lace wedding dress", "ivory satin wedding dress with lace sleeves", "material", [1, 2, 3, 4]),
    ("00018", "T1", "smooth yellow duck body", "yellow duck body with orange polka dots", "pattern", [1, 2, 3]),
    ("00018", "T2", "glossy blue tin toy car", "scratched blue tin toy car", "surface_wear", [1, 2, 3]),
    ("00019", "A1", "loose chestnut horse mane", "braided chestnut horse mane", "hairstyle", [1, 2, 3, 4]),
    ("00019", "C1", "plain dark blue rider jacket", "dark blue rider jacket with gold piping", "trim_pattern", [1, 2, 3, 4]),
    ("00020", "O1", "white marble sculpture", "white marble sculpture with gray veining", "material_pattern", [1]),
    ("00020", "B1", "plain red scarf", "red scarf with thin white stripes", "pattern", [2]),
    ("00021", "O3", "plain white lighthouse", "white lighthouse with red horizontal bands", "pattern", [1, 2, 4]),
    ("00021", "O5", "flat orange-brown seaweed", "wet glossy orange-brown seaweed", "texture", [2, 3]),
    ("00022", "R1", "smooth blue solar panels", "blue solar panels with gold grid lines", "surface_pattern", [1, 2, 3, 5, 6]),
    ("00022", "O11", "steady green sample-tube indicator light", "blinking red sample-tube indicator light", "light_behavior", [5]),
    ("00023", "C1", "matte deep blue leotard", "shiny satin deep blue leotard", "material_finish", [1, 2, 3, 4, 5]),
    ("00023", "O4", "pale pink ballet shoes", "pale pink ballet shoes with crossed ankle ribbons", "accessory_detail", [3]),
    ("00024", "C1", "plain black ramen apprentice outfit", "black ramen apprentice outfit with white sleeve cuffs", "clothing_detail", [1, 2, 3, 4]),
    ("00024", "O7", "orange soft-boiled egg yolk", "bright golden runny egg yolk", "food_texture_color", [3]),
    ("00025", "A2", "blue-green and orange kingfisher plumage", "blue-green and orange kingfisher plumage with white cheek spots", "plumage_pattern", [2]),
    ("00025", "O5", "smooth green foreground leafy plants", "jagged-edged green foreground leafy plants", "leaf_shape", [3]),
    ("00026", "T1", "smooth red clay teapot", "speckled red clay teapot", "surface_pattern", [1]),
    ("00026", "O5", "glossy blue ceramic bowl", "matte blue ceramic bowl", "surface_finish", [2]),
    ("00027", "C1", "plain gray mechanic jacket", "gray mechanic jacket with stitched elbow patches", "clothing_detail", [1, 2, 3, 4]),
    ("00027", "O3", "silver bicycle chain", "black ceramic-coated bicycle chain", "material_finish", [1, 2, 3, 4]),
    ("00028", "C1", "plain light blue gardener shirt", "light blue gardener shirt with rolled sleeves", "clothing_detail", [1, 3, 4, 5]),
    ("00028", "R1", "smooth white and silver gardening robot shell", "white and copper brushed-metal gardening robot shell", "material_finish", [1, 2, 3, 4, 5]),
    ("00029", "C1", "smooth blue alien traveler skin", "blue alien traveler skin with small lavender freckles", "skin_pattern", [1, 5]),
    ("00029", "O5", "blue-white glowing floor tiles", "blue-white glowing floor tiles with pulsing arrow patterns", "light_pattern", [1, 2, 3, 4, 5, 6]),
]


CANONICAL_T3_STYLES = [
    "pixel art style",
    "Makoto Shinkai style",
    "Hayao Miyazaki style",
    "JoJo manga style",
    "cyberpunk style",
    "traditional Chinese ink-wash painting style",
    "oil painting style",
    "American comic-book style",
    "3D realistic animation style",
    "stop-motion clay animation style",
]


T3_STYLES = [
    (f"{vid:05d}", CANONICAL_T3_STYLES[(2 * vid) % len(CANONICAL_T3_STYLES)], CANONICAL_T3_STYLES[(2 * vid + 1) % len(CANONICAL_T3_STYLES)])
    for vid in range(30)
]


T4_STATIC_ADD = [
    ("00000", "small brass order bell", "white ceramic latte cup", [1, 2, 4], "Place a small brass order bell beside the latte cup whenever the counter is visible."),
    ("00001", "orange cone marker", "blue jump bar", [1, 2, 3], "Add an orange cone marker beside the blue jump bar on the agility field."),
    ("00002", "tiny red mailbox", "building-block station", [1, 3], "Add a tiny red mailbox next to the block station in the toy city."),
    ("00003", "yellow sticky note with a star", "whiteboard", [1, 3, 4], "Add a yellow sticky note with a star on the classroom whiteboard."),
    ("00005", "green triage clipboard", "folding stretcher", [1, 4, 5], "Place a green triage clipboard on the stretcher frame during the paramedic sequence."),
    ("00007", "orange safety cone", "yellow drone landing pad", [1, 5], "Add an orange safety cone next to the drone landing pad at the bridgehead."),
    ("00008", "small chalkboard price sign", "fruit stall", [1, 3], "Add a small chalkboard price sign to the fruit stall."),
    ("00009", "red paint rag", "wooden easel", [1, 2, 3], "Hang a red paint rag from the street painter's easel."),
    ("00010", "small blue ceramic saucer", "baguette in paper bag", [2, 4], "Add a small blue ceramic saucer beside the baguette bag on the bakery counter."),
    ("00011", "yellow star sticker", "cardboard rocket", [1, 2, 3, 5], "Add a yellow star sticker to the side of the cardboard rocket."),
    ("00013", "small folded order ticket", "white round plate", [1, 4], "Place a small folded order ticket beside the dessert plate on the steel pass."),
    ("00015", "red shop towel", "workbench", [1, 5], "Add a red shop towel on the garage workbench near the classic car."),
    ("00017", "small pearl jewelry box", "three-panel mirror", [1, 4], "Add a small pearl jewelry box on the fitting-room table near the mirror."),
    ("00019", "blue arena flag", "white jump rails", [1, 2, 3, 4], "Add a blue arena flag beside the green-marked jump."),
    ("00020", "small white museum label card", "marble sculpture pedestal", [1], "Add a small white museum label card on the marble sculpture pedestal."),
    ("00021", "red rescue buoy", "reef rocks", [1, 3], "Add a red rescue buoy on the dark rocks near the coastline."),
    ("00022", "small blue calibration cube", "target rock", [3, 4], "Add a small blue calibration cube beside the rover's target rock."),
    ("00024", "small red noren tag", "wooden counter", [1, 4], "Add a small red noren-style tag hanging from the ramen counter edge."),
    ("00027", "yellow magnetic parts tray", "blue repair stand", [1, 3, 4], "Add a yellow magnetic parts tray clipped to the bicycle repair stand."),
    ("00028", "white plant label stake", "tomato planter", [1, 2, 4, 5], "Add a white plant label stake in the rooftop tomato planter."),
]


T4_STATIC_DELETE = [
    ("00000", "gray cloth", [4], "Remove the gray wiping cloth from the final cafe counter shot while leaving the cup and hand motion intact."),
    ("00001", "number 15 sign", [1, 2], "Remove the white number 15 sign from the agility course."),
    ("00003", "wall clock", [1], "Remove the round wall clock from the robot club classroom."),
    ("00005", "white background car", [4], "Remove the white background car from the hospital entrance shot."),
    ("00007", "tablet interface title text", [4], "Remove the visible 'Bridge Inspection' title text from the tablet interface while keeping the tablet screen active."),
    ("00008", "yellow striped awning", [3], "Remove the yellow striped background awning from the market aisle."),
    ("00009", "black metal street lamp", [1], "Remove the black metal street lamp from the plaza establishing shot."),
    ("00010", "storefront sign reading 'Lattes & Croissants'", [4], "Remove the storefront sign text outside the bakery door."),
    ("00011", "red flag on pole", [1, 5], "Remove the small red flag on the pole beside the clay rocket button base."),
    ("00013", "small metal container", [1], "Remove the small cylindrical metal container from the steel pass counter."),
    ("00014", "stone lantern", [1, 3], "Remove the stone lantern from the koi pond edge while keeping rocks and lotus leaves intact."),
    ("00015", "ceiling fan", [1, 5], "Remove the silver ceiling fan from the classic-car garage ceiling."),
    ("00017", "silver ring on the seamstress hand", [2, 3], "Remove the visible silver ring from the seamstress's hand."),
    ("00018", "paper airplane hanging from the ceiling", [1], "Remove the hanging paper airplane from the toy race setup."),
    ("00020", "exhibition wall text", [2], "Remove the partially visible exhibition wall text behind the bronze mask case."),
    ("00022", "yellow triangular warning marker", [2], "Remove the yellow triangular warning marker from the rover side."),
    ("00023", "green emergency exit sign", [1], "Remove the green emergency exit sign from the dance studio wall."),
    ("00024", "small candle on the ramen counter", [1], "Remove the small candle from the ramen counter."),
    ("00026", "flour jar in the background", [2], "Remove the clear flour jar from the clay kitchen background."),
    ("00029", "ceiling lights", [1, 3, 4], "Remove the round white ceiling lights from the spaceport shots where they appear."),
]


T4_DYNAMIC_ADD = [
    ("00000", "small tabby cafe cat sitting under the counter", "wooden bar counter", [1, 4], "Add a small tabby cafe cat sitting quietly under the wooden counter in the wider cafe shots."),
    ("00001", "second trainer in a blue jacket standing near the tunnel", "yellow tunnel", [1, 3, 4], "Add a second trainer in a blue jacket standing near the yellow tunnel without interfering with the dog run."),
    ("00002", "tiny toy bicyclist circling the plaza", "central plaza", [3], "Add a tiny toy bicyclist circling the central plaza in the overhead toy-city shot."),
    ("00004", "ladybug crawling on the pot rim", "terracotta pot", [2, 3], "Add a small red ladybug crawling along the flower pot rim."),
    ("00006", "small bluebird perched on a branch", "tree roots", [1, 4], "Add a small bluebird perched on a branch above the forest animals."),
    ("00008", "child in a yellow raincoat watching the delivery robot", "pickup window", [4], "Add a child in a yellow raincoat watching the robot at the pickup window."),
    ("00009", "tourist in a white hat pausing behind the painter", "fountain", [1, 3], "Add a tourist in a white hat pausing behind the painter near the fountain."),
    ("00010", "bakery worker in a tan apron behind the display case", "glass display case", [2, 4], "Add a bakery worker in a tan apron behind the glass display case."),
    ("00012", "runner in a silver rain jacket crossing behind the umbrellas", "rainy intersection", [4], "Add a runner in a silver rain jacket crossing behind the umbrella crowd."),
    ("00014", "small turtle resting on a mossy rock", "moss-covered rocks", [1, 3], "Add a small turtle resting on a mossy rock at the pond edge."),
    ("00015", "young apprentice holding a flashlight beside the car", "red classic car", [1, 5], "Add a young apprentice holding a flashlight beside the classic car."),
    ("00016", "tiny winged sprite hovering near the glowing flowers", "glowing flowers", [2, 4], "Add a tiny winged sprite hovering near the glowing flowers."),
    ("00018", "small toy rabbit spectator beside the finish flags", "finish flags", [1, 3], "Add a small toy rabbit spectator beside the finish flags."),
    ("00020", "museum guard in a dark suit standing near the barrier ropes", "barrier ropes", [1], "Add a museum guard in a dark suit standing near the barrier ropes."),
    ("00021", "person in a red raincoat standing far near the lighthouse path", "lighthouse", [2, 4], "Add a tiny distant person in a red raincoat on the lighthouse path."),
    ("00023", "dance instructor in black watching from the mirror edge", "mirror wall", [1, 4, 5], "Add a dance instructor in black watching from the edge of the mirror wall."),
    ("00025", "small turtle swimming near the ducks", "shallow water", [3], "Add a small turtle swimming near the ducks in the wetland water."),
    ("00026", "tiny clay mouse peeking from behind the bowl", "blue bowl", [2], "Add a tiny clay mouse peeking from behind the bowl."),
    ("00027", "shop assistant in a black apron sorting tools", "organized tool wall", [1, 4], "Add a shop assistant in a black apron sorting tools along the workshop wall."),
    ("00029", "small pink alien child waving near the boarding gate", "boarding gate", [5], "Add a small pink alien child waving near the boarding gate."),
]


T4_DYNAMIC_DELETE = [
    ("00000", "additional customer in dark clothing sitting at a table", [4], "Remove the extra dark-clothed customer at the background table while leaving the blue-coat customer and cyclist intact."),
    ("00001", "person in dark clothing standing on the distant path", [1], "Remove the distant person in dark clothing from the agility-course background."),
    ("00002", "small green wind-up robot", [1, 2], "Remove the small green wind-up robot from the toy city while leaving the train route unchanged."),
    ("00003", "two hallway students in dark blue uniforms", [1], "Remove the two hallway students passing behind the robot club room."),
    ("00004", "small black bee", [2], "Remove the small bee from the sunflower watering shot."),
    ("00005", "nurse in white uniform pushing a medical cart", [1, 5], "Remove the background nurse pushing the medical cart, keeping the paramedics and stretcher intact."),
    ("00006", "small yellow bird and green frog", [1, 2], "Remove the tiny yellow bird and green frog from the forest background."),
    ("00007", "large white commercial boat", [3, 5], "Remove the large boat from the river under the bridge."),
    ("00008", "orange cat in the market", [1, 4], "Remove the orange cat from the delivery robot route."),
    ("00009", "gray-black pigeon group", [1, 2], "Remove the pigeons from the plaza around the painter."),
    ("00010", "person in pink shirt outside the bakery", [1, 4], "Remove the passerby outside the bakery glass door."),
    ("00011", "small green spherical alien with googly eyes", [1, 5], "Remove the green alien ball from beside the clay rocket setup."),
    ("00012", "food-delivery scooter rider in bright yellow jacket", [2], "Remove the yellow-jacket scooter rider from the rainy transit shot."),
    ("00014", "blue dragonfly", [2], "Remove the blue dragonfly near the bamboo water spout."),
    ("00015", "second mechanic wearing gray clothing", [1], "Remove the second mechanic from the garage establishing shot."),
    ("00017", "young flower girl with light pink basket", [1], "Remove the flower girl from the bridal fitting-room establishing shot."),
    ("00019", "staff member leading a brown and white pony", [1, 4], "Remove the staff member and pony from the arena background."),
    ("00022", "brown dust devil in the distance", [1, 6], "Remove the distant brown dust devil from the Mars horizon."),
    ("00028", "black delivery drone in the rooftop sky", [1, 5], "Remove the black delivery drone from the rooftop sky while keeping the pedestrians, rooftop gardens, and apartment blocks unchanged."),
    ("00029", "green tall alien and purple cone-headed alien near the boarding gate", [5], "Remove the two extra background aliens near the boarding gate."),
]


T5_SPECS = [
    ("00002", [2, 1, 3]),
    ("00002", [3, 1, 2]),
    ("00004", [2, 1, 3]),
    ("00004", [3, 2, 1]),
    ("00006", [2, 1, 3, 4]),
    ("00006", [3, 2, 1, 4]),
    ("00006", [4, 1, 2, 3]),
    ("00009", [2, 1, 3]),
    ("00009", [3, 1, 2]),
    ("00012", [2, 1, 3, 4]),
    ("00012", [3, 1, 2, 4]),
    ("00012", [4, 1, 2, 3]),
    ("00014", [2, 1, 3]),
    ("00014", [3, 2, 1]),
    ("00015", [2, 1, 3, 4, 5]),
    ("00015", [3, 2, 1, 4, 5]),
    ("00015", [4, 1, 2, 3, 5]),
    ("00015", [5, 1, 2, 3, 4]),
    ("00016", [2, 1, 3, 4]),
    ("00016", [3, 2, 1, 4]),
    ("00016", [4, 1, 2, 3]),
    ("00018", [2, 1, 3]),
    ("00018", [3, 1, 2]),
    ("00020", [2, 1]),
    ("00021", [4, 3, 2, 1]),
    ("00021", [2, 1, 3, 4]),
    ("00021", [3, 1, 2, 4]),
    ("00021", [4, 2, 1, 3]),
    ("00023", [2, 1, 3, 4, 5]),
    ("00023", [3, 2, 1, 4, 5]),
    ("00023", [4, 1, 2, 3, 5]),
    ("00023", [5, 1, 2, 3, 4]),
    ("00025", [2, 1, 3]),
    ("00025", [3, 1, 2]),
    ("00026", [2, 1]),
    ("00029", [6, 5, 4, 3, 2, 1]),
    ("00027", [2, 1, 3, 4]),
    ("00027", [3, 2, 1, 4]),
    ("00027", [4, 1, 2, 3]),
    ("00028", [2, 1, 3, 4, 5]),
    ("00028", [3, 1, 2, 4, 5]),
    ("00028", [4, 2, 1, 3, 5]),
    ("00028", [5, 1, 2, 3, 4]),
    ("00029", [2, 1, 3, 4, 5, 6]),
    ("00029", [3, 2, 1, 4, 5, 6]),
    ("00029", [4, 1, 2, 3, 5, 6]),
    ("00029", [5, 1, 2, 3, 4, 6]),
    ("00029", [6, 1, 2, 3, 4, 5]),
    ("00002", [1, 3, 2]),
    ("00004", [1, 3, 2]),
    ("00006", [1, 3, 2, 4]),
    ("00009", [1, 3, 2]),
    ("00012", [1, 3, 2, 4]),
    ("00014", [1, 3, 2]),
    ("00016", [1, 3, 2, 4]),
    ("00018", [1, 3, 2]),
    ("00021", [1, 3, 2, 4]),
    ("00023", [1, 3, 2, 4, 5]),
    ("00027", [1, 3, 2, 4]),
    ("00028", [1, 3, 2, 4, 5]),
]


T6_SPECS = [
    ("00000", 1, "an over-the-shoulder view from behind the espresso machine", "over-the-shoulder", "slow dolly-in"),
    ("00000", 4, "a low counter-level close shot of the finished latte sliding forward", "low counter-level close shot", "slow push-in"),
    ("00001", 2, "a ground-level tracking shot beside the dog as it clears the jump", "ground-level tracking shot", "fast lateral follow"),
    ("00001", 4, "a tight reaction shot on the trainer's hand giving the treat", "tight reaction shot", "gentle push-in"),
    ("00002", 2, "a side-on macro shot mounted beside the bridge track", "side-on macro", "smooth parallel tracking move"),
    ("00002", 3, "a high top-down map shot of the full circular toy layout", "top-down map shot", "slow clockwise rotation"),
    ("00003", 1, "a low tabletop angle looking past the robot toward the two students", "low tabletop angle", "slow rack-focus push"),
    ("00003", 3, "a robot-eye-level tracking shot along the white table line", "robot-eye-level tracking shot", "steady forward dolly"),
    ("00004", 1, "an extreme soil-level macro shot from between the water droplets", "soil-level macro", "slow creeping push-in"),
    ("00004", 3, "a rotating overhead botanical plate shot of the leaves and bud", "rotating overhead", "slow clockwise orbit"),
    ("00005", 1, "a low-angle shot from the stretcher wheel looking toward the ambulance doors", "low-angle stretcher-wheel shot", "slow dolly-forward"),
    ("00005", 3, "an overhead insert shot looking directly into the open emergency kit", "overhead insert", "slow vertical lift"),
    ("00006", 2, "a water-level close shot beside the raccoon's paws and berries", "water-level close shot", "gentle sideways drift"),
    ("00006", 4, "a wide storybook tableau of all animals around the flower", "wide tableau", "slow pull-back"),
    ("00007", 3, "a drone-camera POV tight on the cracked bridge girder", "drone POV close-up", "slow forward glide"),
    ("00007", 5, "a high aerial return shot following the drone back to the landing pad", "high aerial return shot", "descending arc"),
    ("00008", 2, "a low robot-eye view of the QR code on the cobblestones", "low robot-eye view", "slow tilt-down"),
    ("00008", 4, "an over-the-shoulder shot from behind the recipient's hand at the pickup window", "over-the-shoulder", "slow push-in"),
    ("00009", 2, "an extreme close-up of the brush touching wet watercolor near the fountain sketch", "extreme brush close-up", "small diagonal slide"),
    ("00009", 3, "a reveal shot starting on the painting and tilting up to the plaza behind it", "painting reveal shot", "slow tilt-up"),
    ("00010", 1, "a floor-level shot from under the bakery table looking at the cat", "floor-level shot", "slow push-in"),
    ("00010", 3, "an extreme close-up on the flour paw pressing into the surface", "extreme paw-print close-up", "slow motion push-in"),
    ("00011", 2, "a close side angle on silver tape smoothing over the cardboard rocket crack", "close side angle", "slow left-to-right slide"),
    ("00011", 4, "a dramatic low-angle shot on the astronaut pressing the red launch button", "dramatic low-angle", "quick push-in"),
    ("00012", 1, "a low puddle-reflection shot of the umbrella commuters", "low puddle-reflection shot", "slow forward glide"),
    ("00012", 4, "a high-angle intersection shot over the colorful umbrella crossing", "high-angle intersection shot", "slow crane down"),
    ("00013", 2, "an overhead macro shot centered on the cream domes forming", "overhead macro", "slow vertical lift"),
    ("00013", 4, "a shallow-focus close shot on the bell press beside the plated dessert", "shallow-focus close shot", "slow rack focus"),
    ("00014", 2, "a water-surface macro shot of the dragonfly and bamboo spout ripples", "water-surface macro", "slow lateral drift"),
    ("00014", 3, "an overhead pond shot following the koi around the lotus stems", "overhead pond shot", "slow circular track"),
    ("00015", 2, "a reflection-heavy close-up inside the chrome side mirror", "chrome reflection close-up", "slow push-in"),
    ("00015", 4, "a low wheel-level shot tracking along the whitewall tire and chrome hubcap", "low wheel-level shot", "slow sideways dolly"),
    ("00016", 1, "a sweeping aerial shot around the floating island and glowing tree", "sweeping aerial", "slow 180-degree orbit"),
    ("00016", 4, "a close shot from inside the hollow tree as sparks drift outward", "inside-tree close shot", "slow pull-back"),
    ("00017", 2, "a close shoulder-level shot of the seamstress working the button closure", "shoulder-level close shot", "slow push-in"),
    ("00017", 4, "a mirror-reflection shot showing bride and seamstress from three angles", "mirror-reflection shot", "slow lateral slide"),
    ("00018", 2, "a toy-wheel-level race shot between the duck and car", "toy-wheel-level shot", "fast tracking move"),
    ("00018", 3, "a celebratory close-up on the duck crossing the finish flags", "celebratory close-up", "quick push-in"),
    ("00019", 2, "a low-angle jump shot from beneath the rail as the horse takes off", "low-angle jump shot", "slow upward tilt"),
    ("00019", 3, "an extreme close-up of hooves landing and sand particles flying", "hoof close-up", "slow motion push-in"),
    ("00020", 1, "a high skylight view looking down on the crowd circling the marble sculpture", "high skylight view", "slow crane descent"),
    ("00020", 2, "a tight glass-reflection shot on the bronze mask and passing visitor", "glass-reflection close-up", "slow sideways slide"),
    ("00021", 1, "a wave-level shot looking up as spray bursts over the black rocks", "wave-level shot", "slow tilt-up"),
    ("00021", 4, "a long-lens shot following the lighthouse beam across shells and water", "long-lens beam shot", "slow pan"),
    ("00022", 3, "a close robotic-arm POV approaching the target rock", "robotic-arm POV", "slow mechanical push-in"),
    ("00022", 5, "an extreme close-up of the sample tube sealing with the indicator light", "sample-tube close-up", "slow rack focus"),
    ("00023", 3, "a floor-level close-up tracking the pink ballet shoes over tape marks", "floor-level shoe close-up", "smooth sideways track"),
    ("00023", 5, "a wide mirrored studio shot ending with the dancer framed by window light", "wide mirrored studio shot", "slow pull-back"),
    ("00024", 2, "a steam-level close-up looking across the noodle pot toward the apprentice", "steam-level close-up", "slow push-through"),
    ("00024", 3, "an overhead ramen bowl shot as each topping lands in place", "overhead bowl shot", "slow vertical lift"),
    ("00025", 1, "a waterline telephoto shot following the egret's foot through shallow water", "waterline telephoto", "slow lateral pan"),
    ("00025", 2, "a tight perch close-up on the kingfisher turning its head", "tight perch close-up", "slow push-in"),
    ("00026", 1, "a low tabletop shot facing the teapot as flour puffs outward", "low tabletop shot", "short dolly-in"),
    ("00026", 2, "an overhead bowl shot of the spoon lifting the sugar cube", "overhead bowl shot", "slow clockwise rotation"),
    ("00027", 2, "an extreme drivetrain close-up following the lube along the chain", "drivetrain close-up", "slow macro track"),
    ("00027", 4, "a side tracking shot along the spinning chain as the mechanic tests shifting", "side tracking shot", "steady lateral follow"),
    ("00028", 2, "a close diagnostic shot through the robot scanner over the tomato leaf", "scanner POV close-up", "slow push-in"),
    ("00028", 5, "a warm harvest close-up on the tomato entering the basket", "harvest close-up", "gentle push-in"),
    ("00029", 3, "a low-angle close shot under the spacecraft landing gear as sparks fly", "low-angle spacecraft close-up", "slow push-in"),
    ("00029", 6, "a wide runway shot that tracks the spacecraft lifting into the windowed sky", "wide runway shot", "slow pull-back"),
]


T7_LIGHTING = [
    ("00000", "low golden dusk light"),
    ("00000", "narrow flashlight beam"),
    ("00001", "single amber overhead bulb light"),
    ("00001", "flickering firelight"),
    ("00002", "green neon sign glow"),
    ("00002", "deep blue moonlight"),
    ("00003", "single hard stage spotlight"),
    ("00003", "warm cabaret footlights"),
    ("00004", "midnight blue moonlight mixed with candle glow"),
    ("00004", "flickering candlelight as the main source"),
    ("00005", "cold instrument-panel glow"),
    ("00005", "pulsing red emergency light"),
    ("00006", "blue moonlight"),
    ("00006", "harsh overhead streetlamp light"),
    ("00007", "magenta and cyan neon lighting"),
    ("00007", "rapid white strobe lighting"),
    ("00008", "silver moonlight"),
    ("00008", "deep orange sunset light"),
    ("00009", "icy blue moonlight"),
    ("00009", "helmet headlamp beams"),
    ("00010", "focused white task-lamp light"),
    ("00010", "red neon sign glow"),
    ("00011", "intense orange furnace firelight"),
    ("00011", "dim workshop fire glow"),
    ("00012", "red paper-lantern glow"),
    ("00012", "cold blue moonlight"),
    ("00013", "narrow flashlight beam"),
    ("00013", "green fluorescent hallway light"),
    ("00014", "hard white surgical exam spotlight"),
    ("00014", "ultraviolet exam-lamp glow"),
    ("00015", "small warm desk-lamp pool"),
    ("00015", "cool magnifying workbench light with crisp shadows"),
    ("00016", "orange heat-lamp glow"),
    ("00016", "blue neon strip light"),
    ("00017", "full moonlight across the floor"),
    ("00017", "purple blacklight glow"),
    ("00018", "bright circular ring light"),
    ("00018", "pink neon sign glow"),
    ("00019", "low orange grill firelight"),
    ("00019", "glowing charcoal firelight"),
    ("00020", "silver moonlight"),
    ("00020", "deep orange sunset reflected light"),
    ("00021", "red heat-lamp glow"),
    ("00021", "green surgical overhead light"),
    ("00022", "flashing blue police light"),
    ("00022", "colorful carnival bulb light"),
    ("00023", "green fluorescent light"),
    ("00023", "warm busker spotlight"),
    ("00024", "cool garage fluorescent strip lighting"),
    ("00024", "small handheld work-light beam"),
    ("00025", "silver moonlight"),
    ("00025", "warm propane-burner firelight"),
    ("00026", "white camera-flash bursts"),
    ("00026", "warm chandelier light"),
    ("00027", "single courtroom spotlight"),
    ("00027", "blue moonlight through high windows"),
    ("00028", "campfire light flickering across the scene"),
    ("00028", "deep midnight light with faint fire embers"),
    ("00029", "pink and teal neon cocktail-bar lighting"),
    ("00029", "ultraviolet blacklight"),
]


T8_BACKGROUNDS = [
    ("00000", "cozy cafe interior and street-window background", "snowy alpine lodge cafe with pine ridges outside", ["barista in white shirt and black apron", "white ceramic latte cup", "stainless steel milk pitcher", "black espresso machine"]),
    ("00000", "cozy cafe interior and street-window background", "sunlit seaside kiosk with turquoise water beyond the counter", ["barista in white shirt and black apron", "white ceramic latte cup", "stainless steel milk pitcher", "black espresso machine"]),
    ("00001", "grass agility training field background", "indoor sports arena with blue padded walls", ["Border Collie", "trainer in red jacket", "blue jump bar", "yellow tunnel", "wooden seesaw"]),
    ("00001", "grass agility training field background", "mountain meadow dog park with distant snow peaks", ["Border Collie", "trainer in red jacket", "blue jump bar", "yellow tunnel", "wooden seesaw"]),
    ("00002", "wooden-floor toy city background", "child bedroom carpet city with soft blanket hills", ["red toy train", "green wind-up robot", "blue arch bridge", "train tracks"]),
    ("00002", "wooden-floor toy city background", "miniature tabletop desert town with painted cardboard mesas", ["red toy train", "green wind-up robot", "blue arch bridge", "train tracks"]),
    ("00003", "school robot club classroom background", "modern glass-walled robotics lab", ["short-haired school girl", "glasses-wearing boy", "transparent desktop robot", "screwdriver"]),
    ("00003", "school robot club classroom background", "nighttime science fair booth with poster boards", ["short-haired school girl", "glasses-wearing boy", "transparent desktop robot", "screwdriver"]),
    ("00004", "greenhouse potting bench background", "outdoor botanical garden nursery", ["sunflower seedling", "terracotta pot", "water droplets", "bee"]),
    ("00004", "greenhouse potting bench background", "bright kitchen windowsill herb garden", ["sunflower seedling", "terracotta pot", "water droplets", "bee"]),
    ("00005", "hospital ambulance entrance background", "rainy airport emergency bay", ["two paramedics", "folding stretcher", "ambulance", "oxygen mask"]),
    ("00005", "hospital ambulance entrance background", "snow-covered mountain clinic entrance", ["two paramedics", "folding stretcher", "ambulance", "oxygen mask"]),
    ("00006", "cartoon forest floor background", "sunny meadow picnic clearing", ["squirrel", "raccoon", "fawn", "acorn basket", "white wildflower"]),
    ("00006", "cartoon forest floor background", "glowing mushroom grove at night", ["squirrel", "raccoon", "fawn", "acorn basket", "white wildflower"]),
    ("00007", "steel bridge over river background", "desert canyon bridge inspection site", ["engineer", "black quadcopter drone", "tablet", "bridge crack"]),
    ("00007", "steel bridge over river background", "snowy suspension bridge over an icy river", ["engineer", "black quadcopter drone", "tablet", "bridge crack"]),
    ("00008", "old market street background", "futuristic indoor food court", ["white delivery robot", "paper package", "pickup window", "QR code"]),
    ("00008", "old market street background", "Mediterranean stone alley market", ["white delivery robot", "paper package", "pickup window", "QR code"]),
    ("00009", "classical plaza background", "quiet canal-side square", ["street painter", "wooden easel", "watercolor palette", "finished painting"]),
    ("00009", "classical plaza background", "busy night market art corner", ["street painter", "wooden easel", "watercolor palette", "finished painting"]),
    ("00010", "bakery interior and storefront background", "sunny farmhouse kitchen bakery", ["orange-and-white cat", "baguette bag", "flour paw prints", "croissant"]),
    ("00010", "bakery interior and storefront background", "Paris sidewalk pastry stall", ["orange-and-white cat", "baguette bag", "flour paw prints", "croissant"]),
    ("00011", "handmade cardboard workshop background", "child's bedroom rocket playset", ["clay astronaut", "cardboard rocket", "blue wrench", "red button"]),
    ("00011", "handmade cardboard workshop background", "miniature moon-base craft table", ["clay astronaut", "cardboard rocket", "blue wrench", "red button"]),
    ("00012", "rainy city transit background", "covered airport terminal drop-off lane", ["umbrella commuters", "delivery rider", "bus passengers", "wet pavement"]),
    ("00012", "rainy city transit background", "neon elevated train platform", ["umbrella commuters", "delivery rider", "bus passengers", "wet pavement"]),
    ("00013", "stainless restaurant kitchen background", "marble pastry studio with tall windows", ["chef in white uniform", "white plate", "cream domes", "raspberry sauce", "service bell"]),
    ("00013", "stainless restaurant kitchen background", "dark fine-dining pass with black tile walls", ["chef in white uniform", "white plate", "cream domes", "raspberry sauce", "service bell"]),
    ("00014", "anime koi pond garden background", "snowy temple pond garden", ["golden-red koi", "lotus leaves", "bamboo water spout", "stone lantern"]),
    ("00014", "anime koi pond garden background", "moonlit bamboo courtyard pond", ["golden-red koi", "lotus leaves", "bamboo water spout", "stone lantern"]),
    ("00015", "classic garage workshop background", "open-air vintage car show pavilion", ["red classic car", "mechanic", "chrome side mirror", "whitewall tire"]),
    ("00015", "classic garage workshop background", "desert roadside restoration shed", ["red classic car", "mechanic", "chrome side mirror", "whitewall tire"]),
    ("00016", "floating island cloud-sea background", "aurora-lit sky temple above clouds", ["glowing blue tree", "blue crystals", "waterfalls", "glowing flowers"]),
    ("00016", "floating island cloud-sea background", "sunset ocean of floating lantern clouds", ["glowing blue tree", "blue crystals", "waterfalls", "glowing flowers"]),
    ("00017", "bridal fitting room background", "sunlit palace dressing room", ["bride", "seamstress", "ivory lace wedding dress", "three-panel mirror"]),
    ("00017", "bridal fitting room background", "minimal modern white bridal studio", ["bride", "seamstress", "ivory lace wedding dress", "three-panel mirror"]),
    ("00018", "toy playroom racetrack background", "miniature backyard race track made of cardboard", ["yellow wind-up duck", "blue tin toy car", "finish flags", "building blocks"]),
    ("00018", "toy playroom racetrack background", "moonlit nursery floor racetrack", ["yellow wind-up duck", "blue tin toy car", "finish flags", "building blocks"]),
    ("00019", "sand equestrian arena background", "indoor show-jumping arena with sponsor banners", ["chestnut horse", "rider", "white jump rails", "sand particles"]),
    ("00019", "sand equestrian arena background", "green countryside horse field", ["chestnut horse", "rider", "white jump rails", "sand particles"]),
    ("00020", "museum exhibition hall background", "grand glass-roofed train station gallery", ["marble sculpture", "museum visitors", "bronze mask", "glass display case"]),
    ("00020", "museum exhibition hall background", "minimal white cube contemporary gallery", ["marble sculpture", "museum visitors", "bronze mask", "glass display case"]),
    ("00021", "rocky coastline background", "arctic coast with ice floes", ["reef rocks", "white lighthouse", "seaweed", "seagulls", "fishing boat"]),
    ("00021", "rocky coastline background", "tropical volcanic shoreline at sunset", ["reef rocks", "white lighthouse", "seaweed", "seagulls", "fishing boat"]),
    ("00022", "Mars desert background", "icy Europa plain with Jupiter on the horizon", ["six-wheeled rover", "mechanical arm", "target rock", "sample tube"]),
    ("00022", "Mars desert background", "lunar crater field with Earth hanging overhead", ["six-wheeled rover", "mechanical arm", "target rock", "sample tube"]),
    ("00023", "mirrored dance studio background", "old theater rehearsal stage", ["female dancer", "mirror reflections", "wooden floor", "ballet shoes"]),
    ("00023", "mirrored dance studio background", "sunlit rooftop dance deck", ["female dancer", "mirror reflections", "wooden floor", "ballet shoes"]),
    ("00024", "cozy ramen shop background", "open-air lantern festival noodle stall", ["ramen apprentice", "older ramen master", "ramen bowl", "noodle pot"]),
    ("00024", "cozy ramen shop background", "modern stainless ramen counter", ["ramen apprentice", "older ramen master", "ramen bowl", "noodle pot"]),
    ("00025", "wetland bird habitat background", "misty mountain lake marsh", ["white egret", "kingfisher", "three ducks", "reeds", "shallow water"]),
    ("00025", "wetland bird habitat background", "golden rice-paddy wetland", ["white egret", "kingfisher", "three ducks", "reeds", "shallow water"]),
    ("00026", "clay kitchen tabletop background", "miniature bakery workbench", ["red clay teapot", "wooden spoon", "blue bowl", "flour", "sugar cube"]),
    ("00026", "clay kitchen tabletop background", "sunny dollhouse kitchen counter", ["red clay teapot", "wooden spoon", "blue bowl", "flour", "sugar cube"]),
    ("00027", "bicycle workshop background", "outdoor cycling race service tent", ["female mechanic", "black road bike", "blue repair stand", "silver chain"]),
    ("00027", "bicycle workshop background", "sleek modern bike showroom", ["female mechanic", "black road bike", "blue repair stand", "silver chain"]),
    ("00028", "rooftop garden background", "greenhouse balcony above the city", ["gardener", "gardening robot", "tomato plants", "harvest basket"]),
    ("00028", "rooftop garden background", "desert rooftop hydroponic farm", ["gardener", "gardening robot", "tomato plants", "harvest basket"]),
    ("00029", "spaceport terminal background", "underwater glass travel terminal", ["blue alien traveler", "round suitcase", "round spacecraft", "boarding screen"]),
    ("00029", "spaceport terminal background", "retro moonbase departure lounge", ["blue alien traveler", "round suitcase", "round spacecraft", "boarding screen"]),
]


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def all_shots(vid: str) -> list[int]:
    return [s["shot_id"] for s in SHOTS[vid]]


def frame_shots(vid: str) -> list[dict]:
    return [
        {"shot_id": s["shot_id"], "frame_start": s["frame_start"], "frame_end": s["frame_end"]}
        for s in SHOTS[vid]
    ]


def visible_characters(vlm: dict) -> list[dict]:
    out = []
    for item in vlm.get("characters", []):
        if item.get("source_status") == "source_claim_not_visible":
            continue
        out.append({"id": item.get("id"), "desc": item.get("one_sentence_desc") or item.get("visual_features") or item.get("type")})
    return out


def key_objects(vid: str, vlm: dict, source: dict) -> list[str]:
    names = []
    for obj in vlm.get("objects", []):
        if obj.get("source_status") == "source_claim_not_visible":
            continue
        name = obj.get("name")
        if name and name not in names:
            names.append(name)
    if not names:
        names = list(source.get("key_objects", []))
    return names[:16]


def base_row(vid: str, task: str, idx: int) -> dict:
    source = SOURCE[vid]
    vlm = VLM[vid]
    return {
        "sample_id": f"{vid}_{task}_{idx:04d}",
        "video_id": vid,
        "source_video": f"{vid}.mp4",
        "shots": frame_shots(vid),
        "characters": visible_characters(vlm),
        "key_objects": key_objects(vid, vlm, source),
    }


def local_mask(edit_type: str, source_queries: list[str], edited_queries: list[str]) -> dict:
    return {
        "nep_applicable": True,
        "edit_scope": "local",
        "edit_type": edit_type,
        "source_queries": source_queries,
        "edited_queries": edited_queries,
        "combine": "union",
    }


def global_mask(edit_type: str, reason: str) -> dict:
    return {
        "nep_applicable": False,
        "edit_scope": "global",
        "edit_type": edit_type,
        "source_queries": [],
        "edited_queries": [],
        "combine": "none",
        "reason": reason,
    }


def shot_reorder_mask() -> dict:
    return {
        "nep_applicable": False,
        "edit_scope": "shot_reorder",
        "edit_type": "shot_reorder",
        "source_queries": [],
        "edited_queries": [],
        "combine": "none",
        "reason": "Shot-order edits are temporal/structural rather than spatial local edits.",
    }


def shot_global_mask() -> dict:
    return {
        "nep_applicable": False,
        "edit_scope": "shot_global",
        "edit_type": "cinematic_reshoot",
        "source_queries": [],
        "edited_queries": [],
        "combine": "none",
        "reason": "Cinematic re-shoot changes framing/camera geometry for the whole target shot.",
    }


def build_t1() -> list[dict]:
    rows = []
    for i, (vid, ent, old, new, shots, instruction) in enumerate(T1_DYNAMIC):
        row = base_row(vid, "T1", i)
        row["edit"] = {
            "task_id": "T1",
            "instruction": instruction,
            "target_phrase": new,
            "applicable_shots": shots,
            "mask_queries": local_mask("dynamic_replace", [old], [new]),
            "extra": {"replace_kind": "dynamic", "old_entity": old, "new_entity": new},
            "author": AUTHOR,
            "target_entity": ent,
        }
        rows.append(row)
    offset = len(rows)
    for j, (vid, old, new, shots, instruction) in enumerate(T1_STATIC):
        row = base_row(vid, "T1", offset + j)
        row["edit"] = {
            "task_id": "T1",
            "instruction": instruction,
            "target_phrase": new,
            "applicable_shots": shots,
            "mask_queries": local_mask("static_replace", [old], [new]),
            "extra": {"replace_kind": "static", "op": "replace", "old_object": old, "new_object": new, "anchor": old},
            "author": AUTHOR,
        }
        rows.append(row)
    return rows


def build_t2() -> list[dict]:
    rows = []
    for i, (vid, ent, old, new, category, shots) in enumerate(T2_SPECS):
        row = base_row(vid, "T2", i)
        row["edit"] = {
            "task_id": "T2",
            "instruction": f"Change {old} to {new} in the applicable shots, while preserving the same object identity, motion, and scene layout.",
            "target_phrase": new,
            "target_entity": ent,
            "applicable_shots": shots,
            "mask_queries": local_mask("attribute_edit", [old], [new]),
            "extra": {"attribute_category": category, "old_value": old, "new_value": new},
            "author": AUTHOR,
        }
        rows.append(row)
    return rows


def build_t3() -> list[dict]:
    rows = []
    idx = 0
    for vid, style_a, style_b in T3_STYLES:
        for style in (style_a, style_b):
            row = base_row(vid, "T3", idx)
            row["edit"] = {
                "task_id": "T3",
                "instruction": f"Re-render the entire scene in {style}, preserving the original actions, shot order, character identities, object layout, and camera framing across every shot.",
                "target_phrase": f"{style} look",
                "applicable_shots": all_shots(vid),
                "mask_queries": global_mask("style_transfer", "Whole-frame style edits can legitimately affect the entire frame."),
                "extra": {"render_axis": "style", "style": style},
                "author": AUTHOR,
            }
            rows.append(row)
            idx += 1
    return rows


def build_t4() -> list[dict]:
    rows = []
    idx = 0
    for vid, obj, anchor, shots, instruction in T4_STATIC_ADD:
        row = base_row(vid, "T4", idx)
        row["edit"] = {
            "task_id": "T4",
            "instruction": instruction,
            "target_phrase": obj,
            "applicable_shots": shots,
            "extra": {"op": "add", "object_kind": "static", "old_object": None, "new_object": obj, "anchor": anchor},
            "mask_queries": local_mask("static_add", [], [obj]),
            "author": AUTHOR,
        }
        rows.append(row)
        idx += 1
    for vid, obj, shots, instruction in T4_STATIC_DELETE:
        row = base_row(vid, "T4", idx)
        row["edit"] = {
            "task_id": "T4",
            "instruction": instruction,
            "target_phrase": f"a scene without {obj}",
            "applicable_shots": shots,
            "extra": {"op": "delete", "object_kind": "static", "old_object": obj, "new_object": None, "anchor": obj},
            "mask_queries": local_mask("static_delete", [obj], []),
            "author": AUTHOR,
        }
        rows.append(row)
        idx += 1
    for vid, obj, anchor, shots, instruction in T4_DYNAMIC_ADD:
        row = base_row(vid, "T4", idx)
        row["edit"] = {
            "task_id": "T4",
            "instruction": instruction,
            "target_phrase": obj,
            "applicable_shots": shots,
            "extra": {"op": "add", "object_kind": "dynamic", "old_object": None, "new_object": obj, "anchor": anchor},
            "mask_queries": local_mask("dynamic_add", [], [obj]),
            "author": AUTHOR,
        }
        rows.append(row)
        idx += 1
    for vid, obj, shots, instruction in T4_DYNAMIC_DELETE:
        row = base_row(vid, "T4", idx)
        row["edit"] = {
            "task_id": "T4",
            "instruction": instruction,
            "target_phrase": f"a scene without {obj}",
            "applicable_shots": shots,
            "extra": {"op": "delete", "object_kind": "dynamic", "old_object": obj, "new_object": None, "anchor": obj},
            "mask_queries": local_mask("dynamic_delete", [obj], []),
            "author": AUTHOR,
        }
        rows.append(row)
        idx += 1
    return rows


def build_t5() -> list[dict]:
    rows = []
    for i, (vid, order) in enumerate(T5_SPECS):
        brief = ", then ".join(SHOT_BRIEFS[vid][shot_id - 1] for shot_id in order)
        row = base_row(vid, "T5", i)
        row["edit"] = {
            "task_id": "T5",
            "instruction": f"Reorder the {SOURCE[vid]['scene_id']} scene to shot order {', '.join(map(str, order))}. The edited video should play as: {brief}.",
            "target_phrase": f"shots reordered to {', '.join(map(str, order))}",
            "applicable_shots": all_shots(vid),
            "extra": {"op": "reorder", "new_order": order},
            "author": AUTHOR,
            "mask_queries": shot_reorder_mask(),
        }
        rows.append(row)
    return rows


def build_t6() -> list[dict]:
    rows = []
    for i, (vid, target_shot, target_phrase, framing, camera_move) in enumerate(T6_SPECS):
        lines = []
        for shot_id, brief in enumerate(SHOT_BRIEFS[vid], 1):
            if shot_id == target_shot:
                lines.append(f"Shot {shot_id}: [EDIT] Re-shoot shot {shot_id} of the {SOURCE[vid]['scene_id']} scene as {target_phrase}, with {camera_move}.")
            else:
                lines.append(f"Shot {shot_id}: [KEEP] {brief}")
        row = base_row(vid, "T6", i)
        row["edit"] = {
            "task_id": "T6",
            "instruction": "\n".join(lines),
            "target_phrase": target_phrase,
            "applicable_shots": [target_shot],
            "extra": {"target_shot_id": target_shot, "target_framing": framing, "camera_move": camera_move},
            "mask_queries": shot_global_mask(),
            "author": AUTHOR,
            "instruction_original": f"Re-shoot shot {target_shot} of the {SOURCE[vid]['scene_id']} scene as {target_phrase}, with {camera_move}.",
        }
        rows.append(row)
    return rows


def build_t7() -> list[dict]:
    rows = []
    for i, (vid, lighting) in enumerate(T7_LIGHTING):
        row = base_row(vid, "T7", i)
        row["edit"] = {
            "task_id": "T7",
            "instruction": f"Re-light the scene with {lighting}; keep actions, identities, object layout, framing, and shot order unchanged.",
            "target_phrase": f"{lighting} look",
            "applicable_shots": all_shots(vid),
            "extra": {"render_axis": "lighting", "lighting": lighting},
            "mask_queries": global_mask("lighting_edit", "Whole-frame lighting edits can legitimately affect the entire frame."),
            "author": AUTHOR,
        }
        rows.append(row)
    return rows


def build_t8() -> list[dict]:
    rows = []
    for i, (vid, old_bg, new_bg, preserve) in enumerate(T8_BACKGROUNDS):
        row = base_row(vid, "T8", i)
        row["edit"] = {
            "task_id": "T8",
            "instruction": f"Replace the {old_bg} with {new_bg}, while preserving {', '.join(preserve)}, and the original foreground scale, actions, camera framing, and shot order across every shot.",
            "target_phrase": f"{new_bg} background",
            "applicable_shots": all_shots(vid),
            "extra": {"render_axis": "background", "old_background": old_bg, "new_background": new_bg, "preserve_queries": preserve},
            "mask_queries": {
                "nep_applicable": True,
                "edit_scope": "global_background",
                "edit_type": "background_replace",
                "source_queries": preserve,
                "edited_queries": preserve,
                "combine": "union",
                "score_region": "mask",
                "reason": "T8 replaces the background; NEP scores DINOv2 preservation inside the foreground preserve mask.",
            },
            "author": AUTHOR,
        }
        rows.append(row)
    return rows


def validate_task(task: str, rows: list[dict]) -> list[str]:
    errors = []
    sample_ids = [r["sample_id"] for r in rows]
    if len(sample_ids) != len(set(sample_ids)):
        errors.append(f"{task}: duplicate sample_id")
    for row in rows:
        edit = row["edit"]
        vid = row["video_id"]
        valid_shots = set(all_shots(vid))
        app = edit.get("applicable_shots") or []
        if not set(app).issubset(valid_shots):
            errors.append(f"{row['sample_id']}: invalid applicable_shots {app} for {valid_shots}")
        if task == "T5":
            order = edit["extra"]["new_order"]
            if sorted(order) != sorted(all_shots(vid)):
                errors.append(f"{row['sample_id']}: T5 order {order} does not cover all shots {all_shots(vid)}")
        if task == "T6":
            target = edit["extra"]["target_shot_id"]
            if app != [target]:
                errors.append(f"{row['sample_id']}: T6 applicable_shots mismatch")
    return errors


def distribution(rows: list[dict]) -> dict:
    return {
        "count": len(rows),
        "edit_type": dict(Counter(r["edit"]["mask_queries"]["edit_type"] for r in rows)),
        "videos": dict(Counter(r["video_id"] for r in rows)),
        "shot_span": dict(Counter(len(r["edit"].get("applicable_shots") or []) for r in rows)),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    builders = {
        "T1": build_t1,
        "T2": build_t2,
        "T3": build_t3,
        "T4": build_t4,
        "T5": build_t5,
        "T6": build_t6,
        "T7": build_t7,
        "T8": build_t8,
    }
    manifest = {"author": AUTHOR, "source": str(SOURCE_JSON.relative_to(ROOT)), "vlm_dir": str(VLM_DIR.relative_to(ROOT)), "tasks": {}}
    all_rows = []
    all_errors = []
    for task, builder in builders.items():
        rows = builder()
        errors = validate_task(task, rows)
        all_errors.extend(errors)
        (OUT_DIR / f"{task}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest["tasks"][task] = distribution(rows)
        all_rows.extend(rows)
    manifest["total"] = len(all_rows)
    manifest["validation_errors"] = all_errors
    (OUT_DIR / "all_edit_handoff.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if all_errors:
        for err in all_errors:
            print(err)
        raise SystemExit(1)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


SOURCE_LIST = load_json(SOURCE_JSON)
SOURCE = {f"{item['global_index']:05d}": item for item in SOURCE_LIST}
VLM = {path.stem.split(".")[0]: load_json(path) for path in VLM_DIR.glob("*.vlm.json")}
SHOTS = {}
for path in SHOT_DIR.glob("*.shots.json"):
    data = load_json(path)
    SHOTS[path.stem.split(".")[0]] = data["consensus_shots"]


if __name__ == "__main__":
    main()
