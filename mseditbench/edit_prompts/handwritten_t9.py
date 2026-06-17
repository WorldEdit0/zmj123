"""Hand-written T9 shot-conditioned composite prompts.

T9 targets the multi-shot-specific ability to bind different edit operations
to different shot IDs while preserving untouched shots. Each sample edits a
random-looking subset of shots (1 < m <= n) and draws its per-shot operations
from T1/T2/T4/T6/T8-style edits.

This module builds production JSON by copying source/shots/characters/
key_objects metadata from runs/edit_prompts_v3_vlm/T6.json.
"""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path


AUTHOR = "codex-handwritten-t9-shot-conditioned-20260617"


def _edit(shot_id: int, source_task: str, edit_type: str, target_phrase: str) -> dict:
    return {
        "shot_id": shot_id,
        "source_task": source_task,
        "edit_type": edit_type,
        "target_phrase": target_phrase,
    }


HAND_T9 = [
    {
        "video_id": "00000",
        "lines": [
            "Shot 1: [EDIT] Replace the barista with an elderly woman barista with short silver hair, keeping the espresso extraction into the white cup beside the black espresso machine.",
            "Shot 2: [EDIT] Change the smooth silver stainless steel milk pitcher to a brushed copper milk pitcher while the barista pours steamed milk into the cup.",
            "Shot 3: [KEEP] Keep the overhead close-up of the leaf-shaped latte art forming in the cup unchanged.",
            "Shot 4: [EDIT] Change the shooting style of shot 4 to a close-up shot, keeping the finished latte being wiped, turned, and slid forward while cafe customers sit behind it.",
        ],
        "shot_edits": [
            _edit(1, "T1", "dynamic_replace", "elderly woman barista with silver hair, white shirt, and black apron"),
            _edit(2, "T2", "attribute_edit", "brushed copper milk pitcher"),
            _edit(4, "T6", "cinematic_reshoot", "close-up shot"),
        ],
    },
    {
        "video_id": "00001",
        "lines": [
            "Shot 1: [EDIT] Replace the grass agility field background with an indoor sports arena with blue padded walls, preserving the dog, trainer, obstacles, and starting layout.",
            "Shot 2: [EDIT] Change the solid blue jump bar to a bright red jump bar while the Border Collie jumps over it and lands toward the tunnel.",
            "Shot 3: [EDIT] Change the shooting style of shot 3 to an overhead tracking shot, keeping the dog entering the yellow tunnel and racing out toward the seesaw.",
            "Shot 4: [KEEP] Keep the dog sitting before the trainer and receiving the reward treat unchanged.",
        ],
        "shot_edits": [
            _edit(1, "T8", "background_replace", "indoor sports arena with blue padded walls background"),
            _edit(2, "T2", "attribute_edit", "bright red jump bar"),
            _edit(3, "T6", "cinematic_reshoot", "overhead tracking shot"),
        ],
    },
    {
        "video_id": "00002",
        "lines": [
            "Shot 1: [EDIT] Change the glossy red toy train body to a red toy train body covered with large yellow star stickers as it starts from the striped block station.",
            "Shot 2: [EDIT] Change the shooting style of shot 2 to a side-view close-up, keeping the train crossing the blue arch bridge while the green wind-up robot passes behind it.",
            "Shot 3: [KEEP] Keep the train circling the plaza with lamps and stopping at the second station unchanged.",
        ],
        "shot_edits": [
            _edit(1, "T2", "attribute_edit", "red toy train body covered with large yellow star stickers"),
            _edit(2, "T6", "cinematic_reshoot", "side-view close-up"),
        ],
    },
    {
        "video_id": "00003",
        "lines": [
            "Shot 1: [EDIT] Remove the round wall clock from the robot club classroom while keeping the girl, boy, desktop robot, hallway students, and room layout intact.",
            "Shot 2: [EDIT] Change the shooting style of shot 2 to an overhead close-up, keeping hands tightening a screw in the transparent robot shell.",
            "Shot 3: [EDIT] Change the blue circuit board inside the transparent robot to an orange glowing circuit board while the robot follows the table line and raises its red flag.",
            "Shot 4: [KEEP] Keep the girl celebrating while the boy claps and the robot spins on the table unchanged.",
        ],
        "shot_edits": [
            _edit(1, "T4", "static_delete", "a scene without wall clock"),
            _edit(2, "T6", "cinematic_reshoot", "overhead close-up"),
            _edit(3, "T2", "attribute_edit", "orange glowing circuit board inside the transparent robot"),
        ],
    },
    {
        "video_id": "00004",
        "lines": [
            "Shot 1: [EDIT] Replace the greenhouse potting bench background with an outdoor botanical garden nursery, preserving the sunflower seedling, moist soil, water droplets, and camera framing.",
            "Shot 2: [EDIT] Replace the small black bee with a small orange butterfly circling the sunflower seedling while it is misted in the terracotta pot.",
            "Shot 3: [KEEP] Keep the overhead pot view with four green leaves, central bud, and moving sunlight unchanged.",
        ],
        "shot_edits": [
            _edit(1, "T8", "background_replace", "outdoor botanical garden nursery background"),
            _edit(2, "T1", "dynamic_replace", "small orange butterfly"),
        ],
    },
    {
        "video_id": "00005",
        "lines": [
            "Shot 1: [EDIT] Replace the dark-haired female paramedic with a middle-aged male emergency doctor in the same deep blue uniform with yellow reflective stripes, keeping the stretcher preparation beside the ambulance.",
            "Shot 2: [EDIT] Change the shooting style of shot 2 to a wheel-level close-up, keeping the male paramedic checking and locking the stretcher wheel assembly.",
            "Shot 3: [KEEP] Keep the medical supplies, oxygen mask, gauze, and scissors being checked in the open kit unchanged.",
            "Shot 4: [EDIT] Place a green triage clipboard on the stretcher frame while the paramedics unfold and align the stretcher under the ambulance lights.",
            "Shot 5: [EDIT] Replace the hospital ambulance entrance background with a snow-covered mountain clinic entrance while preserving the stretcher, paramedics, nurse, and hospital-door action.",
        ],
        "shot_edits": [
            _edit(1, "T1", "dynamic_replace", "middle-aged male emergency doctor in the same dark blue paramedic uniform with yellow reflective stripes"),
            _edit(2, "T6", "cinematic_reshoot", "wheel-level close-up"),
            _edit(4, "T4", "static_add", "green triage clipboard"),
            _edit(5, "T8", "background_replace", "snow-covered mountain clinic entrance background"),
        ],
    },
    {
        "video_id": "00006",
        "lines": [
            "Shot 1: [EDIT] Add a small bluebird perched on a branch above the squirrel near the tree hollow and acorn basket.",
            "Shot 2: [EDIT] Change the shooting style of shot 2 to a water-level close-up, keeping the gray raccoon washing red berries in the blue stream.",
            "Shot 3: [KEEP] Keep the spotted fawn lowering its head to smell the white wildflower unchanged.",
            "Shot 4: [EDIT] Replace the cartoon forest floor background with a glowing mushroom grove at night while preserving the gathered forest characters, the white wildflower, and the waving pose.",
        ],
        "shot_edits": [
            _edit(1, "T4", "dynamic_add", "small bluebird perched on a branch"),
            _edit(2, "T6", "cinematic_reshoot", "water-level close-up"),
            _edit(4, "T8", "background_replace", "glowing mushroom grove at night background"),
        ],
    },
    {
        "video_id": "00007",
        "lines": [
            "Shot 1: [EDIT] Change the engineer's flat yellow safety vest to a yellow safety vest with two wide silver reflective bands while the black quadcopter launches from the pad.",
            "Shot 2: [EDIT] Replace the steel bridge over river background with a desert canyon bridge inspection site, preserving the drone, bridge cables, and inspection surfaces.",
            "Shot 3: [EDIT] Change the shooting style of shot 3 to a drone-eye close-up, keeping the drone camera inspecting the rusted crack on the bridge girder above the river.",
            "Shot 4: [KEEP] Keep the engineer reading the tablet heat-map interface with the crack marker unchanged.",
            "Shot 5: [EDIT] Replace the large white boat with a long red cargo barge moving under the bridge as the drone returns toward the landing pad.",
        ],
        "shot_edits": [
            _edit(1, "T2", "attribute_edit", "yellow safety vest with two wide silver reflective bands"),
            _edit(2, "T8", "background_replace", "desert canyon bridge inspection site background"),
            _edit(3, "T6", "cinematic_reshoot", "drone-eye close-up"),
            _edit(5, "T1", "static_replace", "long red cargo barge on the river"),
        ],
    },
    {
        "video_id": "00008",
        "lines": [
            "Shot 1: [EDIT] Replace the orange cat with a small black-and-white market dog near the fruit stall while the white delivery robot leaves with the brown paper package.",
            "Shot 2: [EDIT] Change the shooting style of shot 2 to a robot-eye-level close-up, keeping the robot scanning the QR code on the cobblestone path.",
            "Shot 3: [KEEP] Keep the robot passing crates of tomatoes and market shoppers under striped awnings unchanged.",
            "Shot 4: [EDIT] Add a child in a yellow raincoat watching the robot at the wooden pickup window while the package handoff remains intact.",
        ],
        "shot_edits": [
            _edit(1, "T1", "dynamic_replace", "small black-and-white market dog"),
            _edit(2, "T6", "cinematic_reshoot", "robot-eye-level close-up"),
            _edit(4, "T4", "dynamic_add", "child in a yellow raincoat watching the delivery robot"),
        ],
    },
    {
        "video_id": "00009",
        "lines": [
            "Shot 1: [EDIT] Add a tourist in a white hat pausing behind the painter near the fountain while the easel and plaza composition remain intact.",
            "Shot 2: [EDIT] Change the smooth blue-green painter jacket to a blue-green denim painter jacket while the painter adds watercolor detail near the fountain.",
            "Shot 3: [EDIT] Replace the classical plaza background with a busy night market art corner while preserving the painter, finished painting, easel, and presentation pose.",
        ],
        "shot_edits": [
            _edit(1, "T4", "dynamic_add", "tourist in a white hat pausing behind the painter"),
            _edit(2, "T2", "attribute_edit", "blue-green denim painter jacket"),
            _edit(3, "T8", "background_replace", "busy night market art corner background"),
        ],
    },
    {
        "video_id": "00010",
        "lines": [
            "Shot 1: [EDIT] Change the orange-and-white bakery cat fur to calico bakery cat fur with orange, black, and white patches, preserving the low peek from under the bakery furniture near the flour paw prints.",
            "Shot 2: [EDIT] Add a bakery worker in a tan apron behind the glass display case while the cat sniffs the paper bag holding the baguette.",
            "Shot 3: [KEEP] Keep the cat pressing a fresh flour paw print onto the wooden surface unchanged.",
            "Shot 4: [EDIT] Replace the bakery interior and storefront background with a Paris sidewalk pastry stall, preserving the cat, baguette, croissant, passerby, and doorway pose.",
        ],
        "shot_edits": [
            _edit(1, "T2", "attribute_edit", "calico bakery cat fur with orange, black, and white patches"),
            _edit(2, "T4", "dynamic_add", "bakery worker in a tan apron behind the display case"),
            _edit(4, "T8", "background_replace", "Paris sidewalk pastry stall background"),
        ],
    },
    {
        "video_id": "00011",
        "lines": [
            "Shot 1: [EDIT] Replace the small green alien ball with a tiny silver rolling repair robot beside the clay astronaut and cardboard rocket setup.",
            "Shot 2: [EDIT] Change the shooting style of shot 2 to a side-view close-up, keeping the astronaut taping the crack on the cardboard rocket.",
            "Shot 3: [KEEP] Keep the astronaut tightening the rocket nut with the bright blue wrench unchanged.",
            "Shot 4: [EDIT] Change the soft round cotton-like smoke to large dense puffy white smoke as the astronaut presses the red launch button.",
            "Shot 5: [EDIT] Replace the handmade cardboard workshop background with a lunar crater base with silver domes, preserving the repaired rocket, smoke, astronaut, and small observer.",
        ],
        "shot_edits": [
            _edit(1, "T1", "dynamic_replace", "tiny silver rolling repair robot"),
            _edit(2, "T6", "cinematic_reshoot", "side-view close-up"),
            _edit(4, "T2", "attribute_edit", "large dense puffy white smoke"),
            _edit(5, "T8", "background_replace", "lunar crater base with silver domes background"),
        ],
    },
    {
        "video_id": "00012",
        "lines": [
            "Shot 1: [EDIT] Replace the commuters' dark umbrellas with clear plastic rain ponchos while they move through the wet neon transit entrance.",
            "Shot 2: [KEEP] Keep the yellow-jacket delivery scooter passing the bus stop as passengers move around the bus unchanged.",
            "Shot 3: [EDIT] Replace the rainy city transit background with a neon elevated train platform, preserving the taxis, umbrellas, glowing billboards, rain, and intersection timing.",
            "Shot 4: [EDIT] Add a helicopter with a bright searchlight in the city sky above the traffic intersection while pedestrians with colorful umbrellas cross the reflective street.",
        ],
        "shot_edits": [
            _edit(1, "T1", "static_replace", "clear plastic rain ponchos"),
            _edit(3, "T8", "background_replace", "neon elevated train platform background"),
            _edit(4, "T4", "dynamic_add", "helicopter with a bright searchlight in the city sky above the traffic intersection"),
        ],
    },
    {
        "video_id": "00013",
        "lines": [
            "Shot 1: [EDIT] Replace the head chef with a female pastry chef wearing a black headscarf and white uniform as she sets up the white plate and raises the piping bag.",
            "Shot 2: [EDIT] Change the shooting style of shot 2 to an overhead close-up, keeping the cream domes forming on the dessert.",
            "Shot 3: [EDIT] Change the deep red raspberry sauce dots to dark blackberry-purple sauce dots between the cream domes.",
            "Shot 4: [EDIT] Place a small folded order ticket beside the dessert plate on the steel pass while the chef places the mint leaf, rings the bell, and inspects the dessert.",
        ],
        "shot_edits": [
            _edit(1, "T1", "dynamic_replace", "female pastry chef with a black headscarf and white uniform"),
            _edit(2, "T6", "cinematic_reshoot", "overhead close-up"),
            _edit(3, "T2", "attribute_edit", "dark blackberry-purple sauce dots"),
            _edit(4, "T4", "static_add", "small folded order ticket"),
        ],
    },
    {
        "video_id": "00014",
        "lines": [
            "Shot 1: [EDIT] Replace the anime koi pond garden background with a snowy temple pond garden, preserving the koi, lotus leaves, stone bridge, stone lantern, and water composition.",
            "Shot 2: [EDIT] Replace the blue dragonfly with a small hummingbird hovering beside the bamboo water spout as ripples spread across the pond.",
            "Shot 3: [EDIT] Change the shooting style of shot 3 to an overhead shot, keeping the koi circling under petals, lotus stems, and mossy rocks.",
        ],
        "shot_edits": [
            _edit(1, "T8", "background_replace", "snowy temple pond garden background"),
            _edit(2, "T1", "dynamic_replace", "small hummingbird with iridescent wings"),
            _edit(3, "T6", "cinematic_reshoot", "overhead shot"),
        ],
    },
    {
        "video_id": "00015",
        "lines": [
            "Shot 1: [EDIT] Change the glossy red classic car paint to matte red classic car paint in the garage establishing shot with mechanics and tool shelves.",
            "Shot 2: [EDIT] Change the shooting style of shot 2 to a mirror close-up, keeping the mechanic polishing the chrome side mirror with a cloth.",
            "Shot 3: [KEEP] Keep the wrench tightening a bolt inside the engine bay unchanged.",
            "Shot 4: [KEEP] Keep the whitewall tire and chrome hubcap detail shot unchanged.",
            "Shot 5: [EDIT] Replace the classic garage workshop background with an open-air vintage car show pavilion while preserving the restored car, mechanic, work lights, and final inspection pose.",
        ],
        "shot_edits": [
            _edit(1, "T2", "attribute_edit", "matte red classic car paint"),
            _edit(2, "T6", "cinematic_reshoot", "mirror close-up"),
            _edit(5, "T8", "background_replace", "open-air vintage car show pavilion background"),
        ],
    },
    {
        "video_id": "00016",
        "lines": [
            "Shot 1: [EDIT] Replace the floating island cloud-sea background with an aurora-lit sky temple above clouds, preserving the glowing blue tree and island silhouette.",
            "Shot 2: [EDIT] Change the small multicolored glowing flowers to larger bell-shaped multicolored glowing flowers around the glowing tree roots.",
            "Shot 3: [KEEP] Keep the waterfalls falling from the island edge into the cloud layer unchanged.",
            "Shot 4: [EDIT] Change the shooting style of shot 4 to an interior close-up, keeping the hollow glowing tree releasing white sparks among tall grass leaves.",
        ],
        "shot_edits": [
            _edit(1, "T8", "background_replace", "aurora-lit sky temple above clouds background"),
            _edit(2, "T2", "attribute_edit", "larger bell-shaped multicolored glowing flowers"),
            _edit(4, "T6", "cinematic_reshoot", "interior close-up"),
        ],
    },
    {
        "video_id": "00017",
        "lines": [
            "Shot 1: [EDIT] Add a small pearl jewelry box on the fitting-room table near the mirror while the bride, seamstress, and flower girl remain in place.",
            "Shot 2: [EDIT] Change the ivory lace wedding dress to an ivory satin wedding dress with lace sleeves while the seamstress works on the button closure.",
            "Shot 3: [EDIT] Replace the bride's silver beaded headpiece with a fresh white floral crown while keeping the veil attached as hands arrange it.",
            "Shot 4: [KEEP] Keep the bride and seamstress inspecting the finished fit in the three-panel mirror unchanged.",
        ],
        "shot_edits": [
            _edit(1, "T4", "static_add", "small pearl jewelry box"),
            _edit(2, "T2", "attribute_edit", "ivory satin wedding dress with lace sleeves"),
            _edit(3, "T1", "static_replace", "fresh white floral crown"),
        ],
    },
    {
        "video_id": "00018",
        "lines": [
            "Shot 1: [EDIT] Remove the hanging paper airplane from the toy race setup while keeping the duck, car, racetrack, blocks, and start-line layout intact.",
            "Shot 2: [EDIT] Change the shooting style of shot 2 to a toy-level wide shot, keeping the duck and car racing between colorful blocks under sunlight.",
            "Shot 3: [EDIT] Replace the toy playroom racetrack background with a moonlit nursery floor racetrack, preserving the duck's finish-line win and the cartoon stars above it.",
        ],
        "shot_edits": [
            _edit(1, "T4", "static_delete", "a scene without paper airplane hanging from the ceiling"),
            _edit(2, "T6", "cinematic_reshoot", "toy-level wide shot"),
            _edit(3, "T8", "background_replace", "moonlit nursery floor racetrack background"),
        ],
    },
    {
        "video_id": "00019",
        "lines": [
            "Shot 1: [EDIT] Replace the white jump rails with stacked hay-bale jump blocks while the horse and rider approach the green-marked jump inside the sand arena.",
            "Shot 2: [EDIT] Change the shooting style of shot 2 to a low-angle shot, keeping the chestnut horse taking off over the jump with the rider balanced above it.",
            "Shot 3: [KEEP] Keep the horse landing and kicking up sand particles unchanged.",
            "Shot 4: [EDIT] Add a blue arena flag beside the green-marked jump while the rider guides the horse away and the staff member passes in the background.",
        ],
        "shot_edits": [
            _edit(1, "T1", "static_replace", "stacked hay-bale jump blocks"),
            _edit(2, "T6", "cinematic_reshoot", "low-angle shot"),
            _edit(4, "T4", "static_add", "blue arena flag"),
        ],
    },
    {
        "video_id": "00020",
        "lines": [
            "Shot 1: [EDIT] Replace the museum exhibition hall background with a grand glass-roofed train station gallery, preserving the marble sculpture, visitors, barrier layout, and slow circulation.",
            "Shot 2: [EDIT] Remove the partially visible exhibition wall text behind the bronze mask case while keeping the visitor in the brown coat, red scarf, glass case, and mask intact.",
        ],
        "shot_edits": [
            _edit(1, "T8", "background_replace", "grand glass-roofed train station gallery background"),
            _edit(2, "T4", "static_delete", "a scene without exhibition wall text"),
        ],
    },
    {
        "video_id": "00021",
        "lines": [
            "Shot 1: [EDIT] Change the plain white lighthouse to a white lighthouse with red horizontal bands while waves crash over black reef rocks.",
            "Shot 2: [EDIT] Replace the rocky coastline background with an arctic coast with ice floes, preserving the orange-brown seaweed, tide pool reflection, lighthouse position, and wet rocks.",
            "Shot 3: [EDIT] Replace the small white fishing boat with a red sea kayak on the coastline horizon beyond the rocks and water.",
            "Shot 4: [KEEP] Keep the lighthouse beam sweeping across shells, wet sand, and the evening sea unchanged.",
        ],
        "shot_edits": [
            _edit(1, "T2", "attribute_edit", "white lighthouse with red horizontal bands"),
            _edit(2, "T8", "background_replace", "arctic coast with ice floes background"),
            _edit(3, "T1", "static_replace", "red sea kayak on the horizon"),
        ],
    },
    {
        "video_id": "00022",
        "lines": [
            "Shot 1: [KEEP] Keep the rover approaching the target rock across red sand with a dust devil in the distance unchanged.",
            "Shot 2: [EDIT] Remove the yellow triangular warning marker from the rover side while preserving the wheels, blue solar panel, and red sand motion.",
            "Shot 3: [EDIT] Replace the bright orbiter point with a small meteor streak crossing the sky while the rover extends its mechanical arm toward the target rock.",
            "Shot 4: [KEEP] Keep the drill cutting into the dark rock and throwing red-brown powder unchanged.",
            "Shot 5: [EDIT] Change the steady green sample-tube indicator light to a blinking red sample-tube indicator light as the spherical rock sample is sealed.",
            "Shot 6: [EDIT] Change the shooting style of shot 6 to a long telephoto shot, keeping the rover departing over its tracks while the dust devil remains on the horizon.",
        ],
        "shot_edits": [
            _edit(2, "T4", "static_delete", "a scene without yellow triangular warning marker"),
            _edit(3, "T1", "static_replace", "small meteor streak crossing the sky"),
            _edit(5, "T2", "attribute_edit", "blinking red sample-tube indicator light"),
            _edit(6, "T6", "cinematic_reshoot", "long telephoto shot"),
        ],
    },
    {
        "video_id": "00023",
        "lines": [
            "Shot 1: [EDIT] Remove the green emergency exit sign from the dance studio wall while keeping the dancer, barre, windows, mirrors, and reflected dancers intact.",
            "Shot 2: [EDIT] Replace the mirrored dance studio background with an old theater rehearsal stage, preserving the dancer's pause near the mirror wall and the blue water bottle.",
            "Shot 3: [EDIT] Change the pale pink ballet shoes to pale pink ballet shoes with long ribbons wrapped around the lower legs while the shoes work on the marked wooden floor.",
            "Shot 4: [KEEP] Keep the dancer repeating the phrase while the mirror doubles the movement unchanged.",
            "Shot 5: [KEEP] Keep the dancer finishing the rehearsal sequence in the window light unchanged.",
        ],
        "shot_edits": [
            _edit(1, "T4", "static_delete", "a scene without green emergency exit sign"),
            _edit(2, "T8", "background_replace", "old theater rehearsal stage background"),
            _edit(3, "T2", "attribute_edit", "pale pink ballet shoes with long ribbons wrapped around the lower legs"),
        ],
    },
    {
        "video_id": "00024",
        "lines": [
            "Shot 1: [EDIT] Remove the small candle from the ramen counter while keeping the ramen apprentice, older chef, wooden counter, and shop layout intact.",
            "Shot 2: [EDIT] Change the shooting style of shot 2 to a steam-level close-up, keeping the apprentice lifting noodles from the metal pot with chopsticks and a bamboo strainer.",
            "Shot 3: [EDIT] Replace the cozy ramen shop background with a busy train station noodle stall, preserving the ramen bowl, chashu, scallions, soft-boiled egg, and lucky cat placement.",
            "Shot 4: [KEEP] Keep the apprentice presenting the completed bowl while the older chef supervises unchanged.",
        ],
        "shot_edits": [
            _edit(1, "T4", "static_delete", "a scene without small candle on the ramen counter"),
            _edit(2, "T6", "cinematic_reshoot", "steam-level close-up"),
            _edit(3, "T8", "background_replace", "busy train station noodle stall background"),
        ],
    },
    {
        "video_id": "00025",
        "lines": [
            "Shot 1: [EDIT] Replace the wetland bird habitat background with a misty mountain lake marsh, preserving the white egret, reeds, boardwalk, shallow water, and reflections.",
            "Shot 2: [EDIT] Change the blue-green and orange kingfisher plumage to a kingfisher with a prominent white head crest while it perches on the dead branch.",
            "Shot 3: [EDIT] Add a small turtle swimming near the ducks in the wetland water while keeping the three-duck formation and foreground leafy plants.",
        ],
        "shot_edits": [
            _edit(1, "T8", "background_replace", "misty mountain lake marsh background"),
            _edit(2, "T2", "attribute_edit", "kingfisher with a prominent white head crest"),
            _edit(3, "T4", "dynamic_add", "small turtle swimming near the ducks"),
        ],
    },
    {
        "video_id": "00026",
        "lines": [
            "Shot 1: [EDIT] Change the smooth red clay teapot to a speckled red clay teapot while it puffs white flour on the wooden table.",
            "Shot 2: [EDIT] Replace the glossy blue bowl with a shallow white mixing dish that can still receive the brown sugar cube from the wooden spoon.",
        ],
        "shot_edits": [
            _edit(1, "T2", "attribute_edit", "speckled red clay teapot"),
            _edit(2, "T1", "static_replace", "shallow white mixing dish"),
        ],
    },
    {
        "video_id": "00027",
        "lines": [
            "Shot 1: [EDIT] Add a shop assistant in a black apron sorting tools along the workshop wall while the mechanic checks the black road bike on the blue repair stand.",
            "Shot 2: [EDIT] Change the silver bicycle chain to a black ceramic-coated bicycle chain in the drivetrain close-up as lubricant is applied to the chain and cassette.",
            "Shot 3: [KEEP] Keep the torque wrench tightening the rear derailleur bolt unchanged.",
            "Shot 4: [EDIT] Change the shooting style of shot 4 to a side-view close-up, keeping the mechanic pedaling the bike to test the chain shift while the red cyclist passes again.",
        ],
        "shot_edits": [
            _edit(1, "T4", "dynamic_add", "shop assistant in a black apron sorting tools"),
            _edit(2, "T2", "attribute_edit", "black ceramic-coated bicycle chain"),
            _edit(4, "T6", "cinematic_reshoot", "side-view close-up"),
        ],
    },
    {
        "video_id": "00028",
        "lines": [
            "Shot 1: [EDIT] Add a white plant label stake in the rooftop tomato planter while the gardener and small gardening robot work among the planters.",
            "Shot 2: [EDIT] Change the smooth white and silver gardening robot shell to a white and copper brushed-metal gardening robot shell while it scans tomato leaves with its extendable arm.",
            "Shot 3: [KEEP] Keep the gardener adjusting the spray while the robot backs away from the water mist unchanged.",
            "Shot 4: [EDIT] Replace the rooftop garden background with a snowy mountain glass greenhouse with pine forest outside, preserving the robot, gardener, tomato plants, bamboo stakes, and planter grid.",
            "Shot 5: [EDIT] Replace the wicker tomato basket with a green plastic harvest crate as the gardener places harvested tomatoes into it and the drone crosses the sky.",
        ],
        "shot_edits": [
            _edit(1, "T4", "static_add", "white plant label stake"),
            _edit(2, "T2", "attribute_edit", "white and copper brushed-metal gardening robot shell"),
            _edit(4, "T8", "background_replace", "snowy mountain glass greenhouse with pine forest outside background"),
            _edit(5, "T1", "static_replace", "green plastic harvest crate"),
        ],
    },
    {
        "video_id": "00029",
        "lines": [
            "Shot 1: [EDIT] Replace the gray round suitcase with a floating transparent luggage pod for the blue alien traveler moving through the spaceport.",
            "Shot 2: [EDIT] Change the blue-white glowing floor tiles to blue-white glowing floor tiles with pulsing arrow patterns while the green three-eyed alien opens the backpack at the luggage belt.",
            "Shot 3: [EDIT] Change the shooting style of shot 3 to a low-angle close-up, keeping the maintenance robot welding the underside of the round spacecraft.",
            "Shot 4: [KEEP] Keep the multicolored alien travelers sitting in colorful seats under the space windows unchanged.",
            "Shot 5: [EDIT] Add a small pink alien child waving near the boarding gate while the robot arm taps the boarding screen and alien travelers wait.",
            "Shot 6: [KEEP] Keep the round spacecraft lifting from the glowing runway with blue exhaust flames unchanged.",
        ],
        "shot_edits": [
            _edit(1, "T1", "static_replace", "floating transparent luggage pod"),
            _edit(2, "T2", "attribute_edit", "blue-white glowing floor tiles with pulsing arrow patterns"),
            _edit(3, "T6", "cinematic_reshoot", "low-angle close-up"),
            _edit(5, "T4", "dynamic_add", "small pink alien child waving near the boarding gate"),
        ],
    },
]


def _load_base_by_video(prompt_dir: Path) -> dict[str, dict]:
    t6_path = prompt_dir / "T6.json"
    samples = json.load(open(t6_path))
    base_by_video = {}
    for sample in samples:
        base_by_video.setdefault(sample["video_id"], sample)
    return base_by_video


def _source_task_counts(shot_edits: list[dict]) -> dict[str, int]:
    return dict(sorted(Counter(e["source_task"] for e in shot_edits).items()))


def _validate_sample(sample: dict) -> list[str]:
    errors = []
    shots = sample["shots"]
    lines = sample["edit"]["instruction"].splitlines()
    shot_ids = {int(s["shot_id"]) for s in shots}
    edited_ids = {int(e["shot_id"]) for e in sample["edit"]["extra"]["shot_edits"]}
    if len(lines) != len(shots):
        errors.append(f"{sample['sample_id']}: line count {len(lines)} != shot count {len(shots)}")
    if not (1 < len(edited_ids) <= len(shots)):
        errors.append(f"{sample['sample_id']}: invalid edited-shot count {len(edited_ids)}")
    if not edited_ids.issubset(shot_ids):
        errors.append(f"{sample['sample_id']}: edited shot outside source shots")
    for idx, line in enumerate(lines, start=1):
        prefix = f"Shot {idx}: "
        if not line.startswith(prefix):
            errors.append(f"{sample['sample_id']}: line {idx} missing prefix {prefix!r}")
        is_edit = "[EDIT]" in line
        is_keep = "[KEEP]" in line
        if is_edit == is_keep:
            errors.append(f"{sample['sample_id']}: line {idx} must contain exactly one tag")
        if is_edit and idx not in edited_ids:
            errors.append(f"{sample['sample_id']}: line {idx} marked EDIT but missing from shot_edits")
        if is_keep and idx in edited_ids:
            errors.append(f"{sample['sample_id']}: line {idx} marked KEEP but appears in shot_edits")
    return errors


def build_samples(prompt_dir: Path) -> list[dict]:
    base_by_video = _load_base_by_video(prompt_dir)
    out = []
    errors = []

    for idx, plan in enumerate(HAND_T9):
        video_id = plan["video_id"]
        if video_id not in base_by_video:
            raise KeyError(f"Missing base metadata for video {video_id}")
        sample = copy.deepcopy(base_by_video[video_id])
        sample["sample_id"] = f"{video_id}_T9_{idx:04d}"
        shot_edits = copy.deepcopy(plan["shot_edits"])
        applicable = sorted({int(e["shot_id"]) for e in shot_edits})
        all_shots = [int(s["shot_id"]) for s in sample["shots"]]
        untouched = [sid for sid in all_shots if sid not in applicable]

        sample["edit"] = {
            "task_id": "T9",
            "instruction": "\n".join(plan["lines"]),
            "target_phrase": "shot-conditioned mixed T1/T2/T4/T6/T8 edits",
            "applicable_shots": applicable,
            "mask_queries": {
                "nep_applicable": False,
                "edit_scope": "shot_conditioned_composite",
                "edit_type": "mixed_per_shot",
                "source_queries": [],
                "edited_queries": [],
                "combine": "none",
                "reason": "T9 mixes local, background, and camera edits; preservation should be evaluated by per-shot task-specific metrics.",
            },
            "extra": {
                "edit_type": "shot_conditioned_composite",
                "selection_policy": "handwritten balanced subset, one sample per source video",
                "m": len(applicable),
                "n_shots": len(all_shots),
                "source_tasks": _source_task_counts(shot_edits),
                "shot_edits": shot_edits,
                "untouched_shots": untouched,
            },
            "author": AUTHOR,
        }
        errors.extend(_validate_sample(sample))
        out.append(sample)

    if errors:
        raise ValueError("T9 validation failed:\n" + "\n".join(errors))
    return out


def _task_stats(samples: list[dict]) -> dict:
    task_counter = Counter()
    video_counter = Counter()
    shot_span = Counter()
    m_dist = Counter()
    for sample in samples:
        video_counter[sample["video_id"]] += 1
        m = len(sample["edit"]["applicable_shots"])
        shot_span[str(m)] += 1
        m_dist[str(m)] += 1
        for edit in sample["edit"]["extra"]["shot_edits"]:
            task_counter[edit["source_task"]] += 1
    return {
        "count": len(samples),
        "edit_type": {"shot_conditioned_composite": len(samples)},
        "source_task_ops": dict(sorted(task_counter.items())),
        "videos": dict(sorted(video_counter.items())),
        "shot_span": dict(sorted(shot_span.items())),
        "m_distribution": dict(sorted(m_dist.items())),
    }


def write_outputs(prompt_dir: Path) -> None:
    samples = build_samples(prompt_dir)
    prompt_dir.mkdir(parents=True, exist_ok=True)
    out_path = prompt_dir / "T9.json"
    json.dump(samples, open(out_path, "w"), indent=2, ensure_ascii=False)

    all_path = prompt_dir / "all_edit_handoff.json"
    if all_path.exists():
        all_samples = json.load(open(all_path))
        all_samples = [s for s in all_samples if s.get("edit", {}).get("task_id") != "T9"]
    else:
        all_samples = []
    all_samples.extend(samples)
    json.dump(all_samples, open(all_path, "w"), indent=2, ensure_ascii=False)

    manifest_path = prompt_dir / "manifest.json"
    manifest = json.load(open(manifest_path)) if manifest_path.exists() else {}
    tasks = manifest.setdefault("tasks", {})
    tasks["T9"] = _task_stats(samples)
    manifest["total"] = sum(int(v.get("count", 0)) for v in tasks.values())
    manifest["author"] = manifest.get("author", AUTHOR)
    manifest.setdefault("validation_errors", [])
    json.dump(manifest, open(manifest_path, "w"), indent=2, ensure_ascii=False)

    print(f"Wrote {len(samples)} T9 samples -> {out_path}")
    print(f"Updated {all_path} and {manifest_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt_dir", default="runs/edit_prompts_v3_vlm")
    args = ap.parse_args()
    write_outputs(Path(args.prompt_dir))


if __name__ == "__main__":
    main()
