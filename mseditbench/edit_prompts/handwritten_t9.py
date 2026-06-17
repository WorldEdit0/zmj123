"""Hand-written T9 shot-conditioned composite prompts.

T9 targets two complementary multi-shot editing abilities:

* independent per-shot edits, where each edit is explicitly scoped to only one
  shot and must not leak into the other shots;
* persistent object edits, where two named T1/T2/T4 object edits start at
  specific shots and must continue in every later shot where that object
  appears.

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


def _object_edit(
    edit_id: str,
    source_task: str,
    edit_type: str,
    target_object: str,
    source_phrase: str,
    target_phrase: str,
    start_shot: int,
    applicable_shots: list[int],
) -> dict:
    return {
        "edit_id": edit_id,
        "source_task": source_task,
        "edit_type": edit_type,
        "target_object": target_object,
        "source_phrase": source_phrase,
        "target_phrase": target_phrase,
        "start_shot": start_shot,
        "applicable_shots": applicable_shots,
    }


def _scope_independent_lines(lines: list[str]) -> list[str]:
    scoped = []
    for line in lines:
        shot_id = int(line.split(":", 1)[0].split()[1])
        if "[EDIT]" in line:
            scoped.append(
                f"{line} Apply this edit only to shot {shot_id}; do not carry the changed object, "
                "attribute, camera style, or background into any other shot. If the same object or "
                "setting appears elsewhere, keep its source-video form there."
            )
        else:
            scoped.append(f"{line} Do not inherit any edited change from other shots.")
    return scoped


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


CONTINUITY_T9 = [
    {
        "video_id": "00000",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the barista's plain black apron to a black apron with large white polka dots while espresso is extracted into the white cup. This apron edit must remain whenever the barista is visible in later shots; keep all other objects in their source-video form until named.",
            "Shot 2: [EDIT] Continue the polka-dot apron on the barista, and start persistent edit B: change the smooth silver stainless steel milk pitcher to a brushed copper milk pitcher while steamed milk is poured. This pitcher edit must continue in later shots where the pitcher appears.",
            "Shot 3: [EDIT] Continue the brushed copper milk pitcher if it is visible in the overhead latte-art close-up, while keeping the leaf-shaped latte art, cup placement, and counter motion otherwise unchanged.",
            "Shot 4: [EDIT] Continue the polka-dot apron on the barista if visible while the finished latte is wiped, turned, and slid forward; do not apply the pitcher edit unless the pitcher appears in this shot.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "barista apron", "plain black apron", "black apron with large white polka dots", 1, [1, 2, 4]),
            _object_edit("B", "T2", "attribute_edit", "milk pitcher", "smooth silver stainless steel milk pitcher", "brushed copper milk pitcher", 2, [2, 3]),
        ],
    },
    {
        "video_id": "00001",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the black-and-white Border Collie to solid white Border Collie fur as it begins the agility course. Keep this fur edit on the same dog in every later shot where the dog appears.",
            "Shot 2: [EDIT] Continue the solid white Border Collie, and start persistent edit B: add an orange cone marker beside the jump-bar area while the dog clears the obstacle. Keep the cone marker in later shots where that jump area is visible.",
            "Shot 3: [EDIT] Continue the solid white Border Collie through the tunnel and seesaw path, and keep the orange cone marker beside the jump area if that part of the course is visible.",
            "Shot 4: [EDIT] Continue the solid white Border Collie while it sits before the trainer and receives the reward treat; do not add the cone marker unless the jump area is visible.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "Border Collie", "black-and-white Border Collie fur", "solid white Border Collie fur", 1, [1, 2, 3, 4]),
            _object_edit("B", "T4", "static_add", "orange cone marker", "no cone marker beside the jump-bar area", "orange cone marker", 2, [2, 3]),
        ],
    },
    {
        "video_id": "00002",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the glossy red toy train body to a red body covered with large yellow star stickers as it leaves the striped block station. Keep the star stickers on this train in all later shots.",
            "Shot 2: [EDIT] Continue the yellow-star train across the blue arch bridge, and start persistent edit B: replace the green train carriage with a small wooden cargo wagon while keeping it coupled behind the red toy train. Keep the wooden cargo wagon in later shots where that carriage appears.",
            "Shot 3: [EDIT] Continue both persistent edits as the train circles the plaza and stops at the second station: the red train keeps the large yellow star stickers, and the green carriage remains replaced by the small wooden cargo wagon.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "red toy train body", "glossy red toy train body", "red toy train body covered with large yellow star stickers", 1, [1, 2, 3]),
            _object_edit("B", "T1", "static_replace", "green train carriage", "green train carriage", "small wooden cargo wagon", 2, [2, 3]),
        ],
    },
    {
        "video_id": "00003",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the blue circuit board inside the transparent robot to an orange glowing circuit board while the club room is introduced. Keep this circuit-board edit on the robot whenever the robot appears later.",
            "Shot 2: [EDIT] Continue the robot's orange glowing circuit board if visible while hands tighten the screw in the transparent shell; keep the classroom and students otherwise unchanged.",
            "Shot 3: [EDIT] Continue the orange glowing circuit board as the robot follows the table line, and start persistent edit B: add a yellow sticky note with a star on the classroom whiteboard. Keep the sticky note in later shots where the whiteboard is visible.",
            "Shot 4: [EDIT] Continue the orange glowing circuit board on the spinning robot and keep the yellow star sticky note on the whiteboard if visible while the children celebrate.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "transparent robot circuit board", "blue circuit board inside the transparent robot", "orange glowing circuit board inside the transparent robot", 1, [1, 2, 3, 4]),
            _object_edit("B", "T4", "static_add", "yellow sticky note on the whiteboard", "plain classroom whiteboard", "yellow sticky note with a star", 3, [3, 4]),
        ],
    },
    {
        "video_id": "00004",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the dark wet soil inside the flower pot to white soil while the sunflower seedling is shown on the potting bench. Keep the white soil in every later pot view.",
            "Shot 2: [EDIT] Continue the white soil in the flower pot, and start persistent edit B: add a small red ladybug crawling along the pot rim while the seedling is misted. Keep the ladybug on the pot rim in later shots where that rim is visible.",
            "Shot 3: [EDIT] Continue the white soil in the overhead pot view and keep the small red ladybug on the pot rim if visible; preserve the four green leaves, central bud, and moving sunlight.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "soil inside the flower pot", "dark wet soil inside the flower pot", "white soil inside the flower pot", 1, [1, 2, 3]),
            _object_edit("B", "T4", "dynamic_add", "ladybug on the pot rim", "plain flower pot rim", "small red ladybug crawling along the flower pot rim", 2, [2, 3]),
        ],
    },
    {
        "video_id": "00005",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: replace the dark-haired female paramedic with a middle-aged male emergency doctor in the same dark blue uniform with yellow reflective stripes. Keep this replacement for the same medical worker whenever that worker appears later.",
            "Shot 2: [EDIT] Start persistent edit B: replace the smooth blue stretcher mattress with an orange rescue backboard while the stretcher wheel assembly is checked. Keep the rescue backboard on the stretcher in later shots where the stretcher appears.",
            "Shot 3: [EDIT] Continue the middle-aged male emergency doctor if the same worker is visible while the medical supplies, oxygen mask, gauze, and scissors are checked; do not force the stretcher edit into this kit close-up if the stretcher is absent.",
            "Shot 4: [EDIT] Continue both persistent edits: the same medical worker remains the middle-aged male emergency doctor, and the stretcher keeps the orange rescue backboard while the paramedics unfold and align it.",
            "Shot 5: [EDIT] Continue both persistent edits as the stretcher is loaded at the ambulance entrance: keep the male emergency doctor replacement and the orange rescue backboard on the stretcher.",
        ],
        "object_edits": [
            _object_edit("A", "T1", "dynamic_replace", "female paramedic", "dark-haired female paramedic", "middle-aged male emergency doctor in the same dark blue uniform with yellow reflective stripes", 1, [1, 3, 4, 5]),
            _object_edit("B", "T1", "static_replace", "stretcher mattress", "smooth blue stretcher mattress", "orange rescue backboard", 2, [2, 4, 5]),
        ],
    },
    {
        "video_id": "00006",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the squirrel's plain blue scarf to a red-and-white striped scarf near the tree hollow and acorn basket. Keep this scarf edit on the squirrel whenever it appears later.",
            "Shot 2: [EDIT] Start persistent edit B: replace the gray raccoon with a round brown beaver with a flat tail while it washes berries in the blue stream. Keep the beaver replacement whenever that character appears later.",
            "Shot 3: [KEEP] Keep the spotted fawn smelling the white wildflower unchanged; neither the squirrel scarf edit nor the beaver replacement should be introduced if those characters are absent.",
            "Shot 4: [EDIT] Continue both persistent edits in the group pose: the squirrel keeps the red-and-white striped scarf, and the gray raccoon remains replaced by the round brown beaver with a flat tail.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "squirrel scarf", "plain blue scarf on the squirrel", "red-and-white striped scarf on the squirrel", 1, [1, 4]),
            _object_edit("B", "T1", "dynamic_replace", "gray raccoon", "gray raccoon", "round brown beaver with a flat tail", 2, [2, 4]),
        ],
    },
    {
        "video_id": "00007",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the drone's steady red indicator lights to blinking green indicator lights as the quadcopter launches. Keep the blinking green lights on the drone whenever the drone appears later.",
            "Shot 2: [EDIT] Continue the blinking green drone indicator lights while the drone inspects the bridge cables and surfaces over the river.",
            "Shot 3: [EDIT] Continue the blinking green drone indicator lights in the close bridge-girder inspection view while preserving the rusted crack and camera inspection action.",
            "Shot 4: [EDIT] Continue the drone's blinking green indicator lights if the drone is visible, and start persistent edit B: change the engineer's flat yellow safety vest to a yellow vest with two wide silver reflective bands while the tablet heat-map is read. Keep this vest edit on the engineer later.",
            "Shot 5: [EDIT] Continue both persistent edits during the drone return: the drone keeps blinking green indicator lights, and the engineer keeps the yellow vest with two wide silver reflective bands if visible.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "drone indicator lights", "steady red drone indicator lights", "blinking green drone indicator lights", 1, [1, 2, 3, 4, 5]),
            _object_edit("B", "T2", "attribute_edit", "engineer safety vest", "flat yellow safety vest", "yellow safety vest with two wide silver reflective bands", 4, [4, 5]),
        ],
    },
    {
        "video_id": "00008",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: replace the orange cat with a small black-and-white market dog near the fruit stall while the delivery robot leaves with the package. Keep this dog replacement wherever the same animal appears later.",
            "Shot 2: [EDIT] Start persistent edit B: change the delivery robot's blue circular eyes to blue crescent-shaped robot eyes while it scans the QR code. Keep these crescent eyes on the robot in later shots.",
            "Shot 3: [EDIT] Continue the delivery robot's blue crescent-shaped eyes as it passes tomato crates and market shoppers; keep the dog replacement only if the animal is visible.",
            "Shot 4: [EDIT] Continue both persistent edits at the pickup window: the robot keeps blue crescent-shaped eyes, and the market animal remains the small black-and-white dog during the package handoff if visible.",
        ],
        "object_edits": [
            _object_edit("A", "T1", "dynamic_replace", "orange cat", "orange cat", "small black-and-white market dog", 1, [1, 4]),
            _object_edit("B", "T2", "attribute_edit", "delivery robot eyes", "blue circular robot eyes", "blue crescent-shaped robot eyes", 2, [2, 3, 4]),
        ],
    },
    {
        "video_id": "00009",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the painter's smooth blue-green jacket to a blue-green denim painter jacket near the fountain. Keep this jacket edit on the painter in every later shot.",
            "Shot 2: [EDIT] Continue the blue-green denim painter jacket, and start persistent edit B: replace the wooden easel with a portable tripod display stand while the painter adds watercolor detail. Keep the tripod display stand wherever the painting setup appears later.",
            "Shot 3: [EDIT] Continue both persistent edits during the presentation pose: the painter keeps the blue-green denim jacket, and the finished painting is held on the portable tripod display stand.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "painter jacket", "smooth blue-green painter jacket", "blue-green denim painter jacket", 1, [1, 2, 3]),
            _object_edit("B", "T1", "static_replace", "wooden easel", "wooden easel", "portable tripod display stand", 2, [2, 3]),
        ],
    },
    {
        "video_id": "00010",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the orange-and-white bakery cat fur to calico fur with orange, black, and white patches as the cat peeks near the flour paw prints. Keep the calico fur on this cat in all later shots.",
            "Shot 2: [EDIT] Continue the calico bakery cat, and start persistent edit B: replace the brown paper baguette bag with a small wicker bread basket while the cat sniffs it. Keep the wicker basket in later shots where that bread container appears.",
            "Shot 3: [EDIT] Continue the calico fur on the cat as it presses a fresh flour paw print; do not introduce the wicker basket if the bread container is absent.",
            "Shot 4: [EDIT] Continue both persistent edits near the bakery doorway: the cat remains calico, and the bread container remains the small wicker bread basket if visible.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "bakery cat fur", "orange-and-white bakery cat fur", "calico bakery cat fur with orange, black, and white patches", 1, [1, 2, 3, 4]),
            _object_edit("B", "T1", "static_replace", "baguette bag", "brown paper baguette bag", "small wicker bread basket", 2, [2, 4]),
        ],
    },
    {
        "video_id": "00011",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the smooth white clay astronaut suit to a white suit with a large red circular chest badge beside the cardboard rocket. Keep the red badge on the astronaut suit whenever the astronaut appears later.",
            "Shot 2: [EDIT] Continue the astronaut suit with the red circular chest badge, and start persistent edit B: add a yellow star sticker to the side of the cardboard rocket while the crack is taped. Keep the sticker on the rocket in later shots where the rocket appears.",
            "Shot 3: [EDIT] Continue the red-badged astronaut suit and keep the yellow star sticker on the cardboard rocket if visible while the rocket nut is tightened.",
            "Shot 4: [EDIT] Continue the red-badged astronaut suit as the red launch button is pressed; keep the star sticker only if the rocket side is visible through the smoke.",
            "Shot 5: [EDIT] Continue both persistent edits in the repaired rocket setup: the astronaut suit keeps the red chest badge, and the cardboard rocket keeps the yellow star sticker.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "clay astronaut suit", "smooth white clay astronaut suit", "white clay astronaut suit with a large red circular chest badge", 1, [1, 2, 3, 4, 5]),
            _object_edit("B", "T4", "static_add", "yellow star sticker on cardboard rocket", "plain cardboard rocket side", "yellow star sticker", 2, [2, 3, 5]),
        ],
    },
    {
        "video_id": "00012",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the commuters' plain dark umbrellas to transparent plastic commuter umbrellas at the wet neon transit entrance. Also start persistent edit B: change the glowing neon billboards to glowing neon billboards with magenta frames. Keep both edits in later rainy city shots where the same commuter group or billboards appear.",
            "Shot 2: [KEEP] Keep the yellow-jacket delivery scooter and bus-stop passengers unchanged; do not introduce the transparent-umbrella edit unless the same commuter group is visible, and keep the billboards source-video accurate if they are absent.",
            "Shot 3: [EDIT] Continue the magenta-framed neon billboards on the elevated rainy transit background while preserving the taxis, umbrellas, and intersection timing; do not introduce the transparent commuter umbrellas if that group is absent.",
            "Shot 4: [EDIT] Continue both persistent edits during the crosswalk movement: the commuter group keeps transparent plastic umbrellas, and the city billboards keep magenta frames.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "commuter umbrellas", "plain dark commuter umbrellas", "transparent plastic commuter umbrellas", 1, [1, 4]),
            _object_edit("B", "T2", "attribute_edit", "neon billboards", "glowing neon billboards", "glowing neon billboards with magenta frames", 1, [1, 3, 4]),
        ],
    },
    {
        "video_id": "00013",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: replace the head chef with a female pastry chef wearing a black headscarf and white uniform as the plate is prepared. Keep this chef replacement in every later dessert-plating shot.",
            "Shot 2: [EDIT] Continue the female pastry chef replacement while the cream domes form on the dessert; keep the dessert components otherwise source-video accurate.",
            "Shot 3: [EDIT] Continue the female pastry chef replacement if visible, and start persistent edit B: change the deep red raspberry sauce dots to dark blackberry-purple sauce dots between the cream domes. Keep the purple sauce dots later.",
            "Shot 4: [EDIT] Continue both persistent edits as the dessert is finished: the chef remains the female pastry chef with black headscarf, and the dessert keeps the dark blackberry-purple sauce dots.",
        ],
        "object_edits": [
            _object_edit("A", "T1", "dynamic_replace", "head chef", "head chef", "female pastry chef with a black headscarf and white uniform", 1, [1, 2, 3, 4]),
            _object_edit("B", "T2", "attribute_edit", "raspberry sauce dots", "deep red raspberry sauce dots", "dark blackberry-purple sauce dots", 3, [3, 4]),
        ],
    },
    {
        "video_id": "00014",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the koi scales to golden-red scales with larger black-edged markings in the pond establishing view. Keep these markings on the koi in later shots.",
            "Shot 2: [EDIT] Continue the koi with larger black-edged markings, and start persistent edit B: add a small turtle resting on a mossy rock at the pond edge while the water spout creates ripples. Keep the turtle in later pond-edge shots.",
            "Shot 3: [EDIT] Continue both persistent edits in the overhead pond view: the koi keep larger black-edged markings, and the small turtle remains on the mossy rock if the pond edge is visible.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "koi scales", "golden-red koi scales", "golden-red koi scales with larger black-edged markings", 1, [1, 2, 3]),
            _object_edit("B", "T4", "dynamic_add", "small turtle on mossy rock", "empty mossy pond-edge rock", "small turtle resting on a mossy rock", 2, [2, 3]),
        ],
    },
    {
        "video_id": "00015",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the glossy red classic car paint to matte red paint in the garage establishing shot. Also start persistent edit B: add a young apprentice holding a flashlight beside the car. Keep both edits in later shots where the car or apprentice area is visible.",
            "Shot 2: [EDIT] Continue the matte red classic car paint during the mirror polishing close-up; keep the young apprentice edit only if that person is visible.",
            "Shot 3: [EDIT] Continue the matte red classic car paint if the car body is visible while the engine-bay bolt is tightened; do not force the apprentice into this close-up if absent.",
            "Shot 4: [EDIT] Continue the matte red classic car paint if visible in the tire and chrome hubcap detail shot; keep the tire and hubcap geometry unchanged.",
            "Shot 5: [EDIT] Continue both persistent edits during the final inspection: the restored car keeps matte red paint, and the young apprentice with a flashlight remains beside the car if visible.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "classic car paint", "glossy red classic car paint", "matte red classic car paint", 1, [1, 2, 3, 4, 5]),
            _object_edit("B", "T4", "dynamic_add", "young apprentice holding a flashlight", "garage area beside the classic car", "young apprentice holding a flashlight beside the car", 1, [1, 5]),
        ],
    },
    {
        "video_id": "00016",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the glowing tree's blue leaves to violet glowing leaves on the floating island. Keep the violet leaves on the same tree in later shots.",
            "Shot 2: [EDIT] Continue the violet glowing tree leaves, and start persistent edit B: change the small multicolored glowing flowers to larger bell-shaped multicolored glowing flowers around the tree roots. Keep these larger flowers in later shots where the flowers appear.",
            "Shot 3: [EDIT] Continue the violet glowing tree leaves if the tree canopy is visible while waterfalls fall into the cloud layer; do not introduce the flower edit if the flowers are absent.",
            "Shot 4: [EDIT] Continue both persistent edits inside the glowing tree scene: the tree keeps violet glowing leaves, and the flowers remain larger bell-shaped multicolored flowers if visible.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "glowing tree leaves", "blue glowing tree leaves", "violet glowing tree leaves", 1, [1, 2, 3, 4]),
            _object_edit("B", "T2", "attribute_edit", "glowing flowers", "small multicolored glowing flowers", "larger bell-shaped multicolored glowing flowers", 2, [2, 4]),
        ],
    },
    {
        "video_id": "00017",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the seamstress's plain blue shirt to a blue shirt with a white tailor apron over it while the bridal fitting room is introduced. Keep this seamstress outfit edit in later shots.",
            "Shot 2: [EDIT] Continue the seamstress outfit edit, and start persistent edit B: change the ivory lace wedding dress to an ivory satin wedding dress with lace sleeves while the button closure is adjusted. Keep this dress edit on the bride in later shots.",
            "Shot 3: [EDIT] Continue both persistent edits while the veil is arranged: the seamstress keeps the blue shirt with white tailor apron, and the bride keeps the ivory satin dress with lace sleeves.",
            "Shot 4: [EDIT] Continue both persistent edits in the three-panel mirror inspection: the seamstress outfit and the bride's satin dress with lace sleeves remain consistent.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "seamstress shirt", "plain blue seamstress shirt", "blue seamstress shirt with a white tailor apron over it", 1, [1, 2, 3, 4]),
            _object_edit("B", "T2", "attribute_edit", "wedding dress", "ivory lace wedding dress", "ivory satin wedding dress with lace sleeves", 2, [2, 3, 4]),
        ],
    },
    {
        "video_id": "00018",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the smooth yellow wind-up duck body to a yellow duck body with orange polka dots at the toy race start. Keep the polka dots on the duck in later shots.",
            "Shot 2: [EDIT] Continue the polka-dot duck, and start persistent edit B: change the glossy blue tin toy car to a blue tin toy car with a large white racing number on the side while it races between colorful blocks. Keep this racing number on the car later.",
            "Shot 3: [EDIT] Continue both persistent edits at the finish: the duck keeps its orange polka dots, and the blue tin car keeps the large white racing number if visible.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "wind-up duck body", "smooth yellow duck body", "yellow duck body with orange polka dots", 1, [1, 2, 3]),
            _object_edit("B", "T2", "attribute_edit", "blue tin toy car", "glossy blue tin toy car", "blue tin toy car with a large white racing number on the side", 2, [2, 3]),
        ],
    },
    {
        "video_id": "00019",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the chestnut horse's loose mane to a braided chestnut mane as horse and rider approach the jump. Keep the braided mane on the horse in later shots.",
            "Shot 2: [EDIT] Continue the braided chestnut mane, and start persistent edit B: replace the white jump rails with stacked hay-bale jump blocks while the horse takes off. Keep the hay-bale jump blocks in later shots where the obstacle appears.",
            "Shot 3: [EDIT] Continue the braided chestnut mane as the horse lands and kicks up sand; keep the hay-bale jump blocks only if the obstacle remains visible.",
            "Shot 4: [EDIT] Continue both persistent edits as the rider guides the horse away: the horse keeps the braided mane, and the jump remains stacked hay-bale blocks if visible.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "chestnut horse mane", "loose chestnut horse mane", "braided chestnut horse mane", 1, [1, 2, 3, 4]),
            _object_edit("B", "T1", "static_replace", "white jump rails", "white jump rails", "stacked hay-bale jump blocks", 2, [2, 3, 4]),
        ],
    },
    {
        "video_id": "00020",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the polished wooden museum floor to a dark herringbone wooden floor while visitors circulate around the marble sculpture and barrier. Also start persistent edit B: add a small white museum label card beside the displayed artifact. Keep both edits in later museum shots.",
            "Shot 2: [EDIT] Continue the dark herringbone wooden floor near the bronze mask case, and continue the small white museum label card beside the displayed mask case while keeping the visitor, red scarf, glass case, and bronze mask otherwise unchanged.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "museum wooden floor", "polished wooden museum floor", "dark herringbone wooden floor", 1, [1, 2]),
            _object_edit("B", "T4", "static_add", "museum label card", "displayed artifacts without a small white label card", "small white museum label card", 1, [1, 2]),
        ],
    },
    {
        "video_id": "00021",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the plain white lighthouse to a white lighthouse with red horizontal bands as waves crash over black reef rocks. Keep the red bands on the lighthouse in later shots.",
            "Shot 2: [EDIT] Continue the red-banded lighthouse, and start persistent edit B: change the flat orange-brown seaweed to thick long tangled orange-brown seaweed around the tide pool. Keep this seaweed edit in later tide-pool shots.",
            "Shot 3: [EDIT] Continue the thick tangled orange-brown seaweed along the coastline horizon view; keep the lighthouse red bands only if the lighthouse is visible.",
            "Shot 4: [EDIT] Continue the red-banded lighthouse as its beam sweeps across shells, wet sand, and the evening sea; the tangled seaweed edit continues only if seaweed is visible.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "lighthouse", "plain white lighthouse", "white lighthouse with red horizontal bands", 1, [1, 2, 4]),
            _object_edit("B", "T2", "attribute_edit", "orange-brown seaweed", "flat orange-brown seaweed", "thick long tangled orange-brown seaweed", 2, [2, 3]),
        ],
    },
    {
        "video_id": "00022",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the rover's smooth blue solar panels to blue solar panels with gold grid lines as it approaches the target rock. Keep these gold grid lines on the solar panels in later rover shots.",
            "Shot 2: [EDIT] Continue the rover's blue solar panels with gold grid lines while preserving the wheels, side details, and red sand motion.",
            "Shot 3: [EDIT] Continue the gold-grid solar panels, and start persistent edit B: add a small blue calibration cube beside the rover's target rock as the mechanical arm extends. Keep the cube beside the target rock in later rock-analysis shots.",
            "Shot 4: [EDIT] Continue the small blue calibration cube beside the target rock while the drill cuts into the dark rock and throws red-brown powder; keep the solar-panel edit only if the rover panels are visible.",
            "Shot 5: [EDIT] Continue the rover's gold-grid solar panels if visible as the spherical rock sample is sealed; do not introduce the calibration cube if the target rock area is absent.",
            "Shot 6: [EDIT] Continue the rover's gold-grid solar panels as it departs over its tracks with the dust devil on the horizon.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "rover solar panels", "smooth blue solar panels", "blue solar panels with gold grid lines", 1, [1, 2, 3, 5, 6]),
            _object_edit("B", "T4", "static_add", "blue calibration cube", "empty area beside the rover target rock", "small blue calibration cube beside the rover's target rock", 3, [3, 4]),
        ],
    },
    {
        "video_id": "00023",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the dancer's matte deep blue leotard to a shiny satin deep blue leotard near the barre and mirror wall. Keep the satin leotard on the dancer in all later shots.",
            "Shot 2: [EDIT] Continue the shiny satin deep blue leotard while the dancer pauses near the mirror wall and blue water bottle.",
            "Shot 3: [EDIT] Continue the shiny satin deep blue leotard while the ballet shoes work on the marked wooden floor; keep shoes and floor markings otherwise source-video accurate.",
            "Shot 4: [EDIT] Continue the satin leotard, and start persistent edit B: add a dance instructor in black watching from the edge of the mirror wall while the dancer repeats the phrase. Keep the instructor in later shots where that mirror edge is visible.",
            "Shot 5: [EDIT] Continue both persistent edits as the rehearsal sequence finishes in the window light: the dancer keeps the shiny satin leotard, and the instructor in black remains near the mirror edge if visible.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "dancer leotard", "matte deep blue leotard", "shiny satin deep blue leotard", 1, [1, 2, 3, 4, 5]),
            _object_edit("B", "T4", "dynamic_add", "dance instructor at mirror edge", "empty mirror-wall edge", "dance instructor in black watching from the mirror edge", 4, [4, 5]),
        ],
    },
    {
        "video_id": "00024",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the ramen apprentice's plain black outfit to a black outfit with white sleeve cuffs at the counter. Keep this outfit edit on the apprentice in later shots.",
            "Shot 2: [EDIT] Continue the apprentice's black outfit with white sleeve cuffs while noodles are lifted from the metal pot with chopsticks and a bamboo strainer.",
            "Shot 3: [EDIT] Continue the apprentice outfit edit, and start persistent edit B: replace the white ramen bowl with red rim with a black ceramic donburi pot that holds the ramen, chashu, scallions, soft-boiled egg, and broth. Keep the donburi pot later.",
            "Shot 4: [EDIT] Continue both persistent edits as the completed bowl is presented: the apprentice keeps white sleeve cuffs, and the ramen remains in the black ceramic donburi pot.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "ramen apprentice outfit", "plain black ramen apprentice outfit", "black ramen apprentice outfit with white sleeve cuffs", 1, [1, 2, 3, 4]),
            _object_edit("B", "T1", "static_replace", "ramen bowl", "white ramen bowl with a red rim", "black ceramic donburi pot", 3, [3, 4]),
        ],
    },
    {
        "video_id": "00025",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the shallow wetland water reflections to warm golden water reflections around the white egret. Also start persistent edit B: change the green reeds to green reeds with pale lavender tips. Keep both edits in later wetland shots where water or reeds appear.",
            "Shot 2: [EDIT] Continue the warm golden water reflections and the pale-lavender-tipped reeds if they are visible behind the kingfisher on the dead branch; keep the kingfisher itself unchanged.",
            "Shot 3: [EDIT] Continue both persistent edits around the ducks: the wetland water keeps warm golden reflections, and the reeds/foreground leafy plants keep pale lavender tips where visible.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "wetland water reflections", "shallow wetland water reflections", "warm golden water reflections", 1, [1, 2, 3]),
            _object_edit("B", "T2", "attribute_edit", "green reeds and foreground leafy plants", "green reeds and foreground leafy plants", "green reeds and foreground leafy plants with pale lavender tips", 1, [1, 2, 3]),
        ],
    },
    {
        "video_id": "00026",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: replace the rolling red cherry tomato with a small yellow lemon while the red clay teapot puffs white flour. Also start persistent edit B: change the plain wooden table surface to a wooden table covered with a light blue checkered cloth. Keep both edits in later clay-kitchen shots.",
            "Shot 2: [EDIT] Continue the small yellow lemon and the light blue checkered tablecloth while the wooden spoon drops the brown sugar cube into the glossy blue bowl; keep the bowl itself in its source-video form.",
        ],
        "object_edits": [
            _object_edit("A", "T1", "dynamic_replace", "rolling red cherry tomato", "rolling red cherry tomato", "small yellow lemon", 1, [1, 2]),
            _object_edit("B", "T2", "attribute_edit", "wooden table surface", "plain wooden table surface", "wooden table covered with a light blue checkered cloth", 1, [1, 2]),
        ],
    },
    {
        "video_id": "00027",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the mechanic's plain gray jacket to a gray mechanic jacket with black tool suspenders while the black road bike is checked on the blue repair stand. Keep this jacket edit on the mechanic in later shots.",
            "Shot 2: [EDIT] Continue the mechanic jacket edit if visible, and start persistent edit B: change the silver bicycle chain to a black ceramic-coated bicycle chain in the drivetrain close-up. Keep the black ceramic-coated chain in later bike shots.",
            "Shot 3: [EDIT] Continue the black ceramic-coated bicycle chain if visible while the torque wrench tightens the rear derailleur bolt; keep the mechanic jacket edit if the mechanic is visible.",
            "Shot 4: [EDIT] Continue both persistent edits while the mechanic pedals the bike to test the chain shift: the mechanic keeps black tool suspenders, and the bicycle keeps the black ceramic-coated chain.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "mechanic jacket", "plain gray mechanic jacket", "gray mechanic jacket with black tool suspenders", 1, [1, 2, 3, 4]),
            _object_edit("B", "T2", "attribute_edit", "bicycle chain", "silver bicycle chain", "black ceramic-coated bicycle chain", 2, [2, 3, 4]),
        ],
    },
    {
        "video_id": "00028",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the smooth white and silver gardening robot shell to a white and copper brushed-metal shell while the gardener and robot work among rooftop planters. Keep this robot shell edit in later shots.",
            "Shot 2: [EDIT] Continue the white and copper brushed-metal robot shell, and start persistent edit B: add a white plant label stake in the rooftop tomato planter while the robot scans tomato leaves. Keep the label stake in later planter shots.",
            "Shot 3: [EDIT] Continue the robot's white and copper brushed-metal shell while it backs away from the water mist; do not force the plant label if the tomato planter is not visible.",
            "Shot 4: [EDIT] Continue both persistent edits in the planter grid: the robot keeps the copper brushed-metal shell, and the tomato planter keeps the white plant label stake.",
            "Shot 5: [EDIT] Continue both persistent edits during the harvest: keep the robot shell white and copper brushed metal if visible, and keep the white plant label stake in the tomato planter if the planter is visible.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "gardening robot shell", "smooth white and silver gardening robot shell", "white and copper brushed-metal gardening robot shell", 1, [1, 2, 3, 4, 5]),
            _object_edit("B", "T4", "static_add", "white plant label stake", "plain rooftop tomato planter", "white plant label stake", 2, [2, 4, 5]),
        ],
    },
    {
        "video_id": "00029",
        "mode": "persistent_object_edit",
        "lines": [
            "Shot 1: [EDIT] Start persistent edit A: change the blue alien traveler's smooth blue skin to blue skin with bold purple stripes while moving through the spaceport. Keep these purple stripes on the same alien whenever it appears later.",
            "Shot 2: [EDIT] Start persistent edit B: change the blue-white glowing floor tiles to blue-white glowing floor tiles with pulsing arrow patterns while the green three-eyed alien opens the backpack. Keep the arrow-pattern floor tiles in later spaceport shots.",
            "Shot 3: [EDIT] Continue the pulsing arrow patterns on the blue-white glowing floor tiles if the floor is visible while the maintenance robot welds the spacecraft underside; keep the striped blue alien edit only if that traveler is visible.",
            "Shot 4: [EDIT] Continue the pulsing arrow patterns on the glowing floor tiles under the seated alien travelers if visible; keep the blue alien's purple stripes only if that same traveler appears.",
            "Shot 5: [EDIT] Continue both persistent edits near the boarding gate: the blue alien traveler keeps bold purple stripes, and the glowing floor tiles keep pulsing arrow patterns.",
            "Shot 6: [EDIT] Continue the pulsing arrow patterns on the glowing runway or floor tiles as the round spacecraft lifts with blue exhaust flames; the blue alien stripes continue only if that traveler is visible.",
        ],
        "object_edits": [
            _object_edit("A", "T2", "attribute_edit", "blue alien traveler skin", "smooth blue alien traveler skin", "blue alien traveler skin with bold purple stripes", 1, [1, 5]),
            _object_edit("B", "T2", "attribute_edit", "blue-white glowing floor tiles", "blue-white glowing floor tiles", "blue-white glowing floor tiles with pulsing arrow patterns", 2, [2, 3, 4, 5, 6]),
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


def _expand_object_edits(object_edits: list[dict]) -> list[dict]:
    shot_edits = []
    for edit in object_edits:
        for shot_id in edit["applicable_shots"]:
            shot_edits.append(
                {
                    "shot_id": shot_id,
                    "object_edit_id": edit["edit_id"],
                    "source_task": edit["source_task"],
                    "edit_type": edit["edit_type"],
                    "target_object": edit["target_object"],
                    "target_phrase": edit["target_phrase"],
                    "continuation": shot_id != edit["start_shot"],
                }
            )
    return sorted(shot_edits, key=lambda e: (e["shot_id"], e["object_edit_id"]))


def _validate_sample(sample: dict) -> list[str]:
    errors = []
    shots = sample["shots"]
    lines = sample["edit"]["instruction"].splitlines()
    shot_ids = {int(s["shot_id"]) for s in shots}
    extra = sample["edit"]["extra"]
    mode = extra.get("mode", "independent_per_shot")
    edited_ids = set(sample["edit"]["applicable_shots"])
    if len(lines) != len(shots):
        errors.append(f"{sample['sample_id']}: line count {len(lines)} != shot count {len(shots)}")
    if not (1 < len(edited_ids) <= len(shots)):
        errors.append(f"{sample['sample_id']}: invalid edited-shot count {len(edited_ids)}")
    if not edited_ids.issubset(shot_ids):
        errors.append(f"{sample['sample_id']}: edited shot outside source shots")
    if mode == "independent_per_shot":
        logical_edits = extra["shot_edits"]
        logical_ids = {int(e["shot_id"]) for e in logical_edits}
        if logical_ids != edited_ids:
            errors.append(f"{sample['sample_id']}: independent applicable shots do not match shot_edits")
    elif mode == "persistent_object_edit":
        object_edits = extra.get("object_edits", [])
        if len(object_edits) != 2:
            errors.append(f"{sample['sample_id']}: persistent mode must define exactly two object edits")
        for obj in object_edits:
            if obj["source_task"] not in {"T1", "T2", "T4"}:
                errors.append(f"{sample['sample_id']}: persistent edit uses disallowed source task {obj['source_task']}")
            if obj["start_shot"] not in obj["applicable_shots"]:
                errors.append(f"{sample['sample_id']}: object edit {obj['edit_id']} start shot missing from applicable shots")
            if any(int(sid) not in shot_ids for sid in obj["applicable_shots"]):
                errors.append(f"{sample['sample_id']}: object edit {obj['edit_id']} has shot outside source shots")
        object_ids = {int(sid) for obj in object_edits for sid in obj["applicable_shots"]}
        if object_ids != edited_ids:
            errors.append(f"{sample['sample_id']}: persistent applicable shots do not match object_edits")
    else:
        errors.append(f"{sample['sample_id']}: unknown T9 mode {mode}")
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

    plans = [dict(plan, mode="independent_per_shot") for plan in HAND_T9] + CONTINUITY_T9

    for idx, plan in enumerate(plans):
        video_id = plan["video_id"]
        if video_id not in base_by_video:
            raise KeyError(f"Missing base metadata for video {video_id}")
        sample = copy.deepcopy(base_by_video[video_id])
        sample["sample_id"] = f"{video_id}_T9_{idx:04d}"
        mode = plan.get("mode", "independent_per_shot")
        object_edits = copy.deepcopy(plan.get("object_edits", []))
        if mode == "persistent_object_edit":
            logical_edits = object_edits
            shot_edits = _expand_object_edits(object_edits)
            applicable = sorted({int(e["shot_id"]) for e in shot_edits})
            lines = plan["lines"]
            target_phrase = "persistent two-object T1/T2/T4 edits"
            edit_scope = "persistent_object_composite"
            edit_type = "persistent_two_object_edits"
            selection_policy = "handwritten persistent two-object subset, one sample per source video"
            reason = "T9 persistent mode mixes two local object edits and evaluates whether each edited object remains edited in later shots where it appears."
        else:
            shot_edits = copy.deepcopy(plan["shot_edits"])
            logical_edits = shot_edits
            applicable = sorted({int(e["shot_id"]) for e in shot_edits})
            lines = _scope_independent_lines(plan["lines"])
            target_phrase = "shot-local mixed T1/T2/T4/T6/T8 edits"
            edit_scope = "shot_conditioned_composite"
            edit_type = "mixed_per_shot"
            selection_policy = "handwritten balanced shot-local subset, one sample per source video"
            reason = "T9 shot-local mode mixes local, background, and camera edits; each edit is explicitly constrained to its own shot."
        all_shots = [int(s["shot_id"]) for s in sample["shots"]]
        untouched = [sid for sid in all_shots if sid not in applicable]

        sample["edit"] = {
            "task_id": "T9",
            "instruction": "\n".join(lines),
            "target_phrase": target_phrase,
            "applicable_shots": applicable,
            "mask_queries": {
                "nep_applicable": False,
                "edit_scope": edit_scope,
                "edit_type": edit_type,
                "source_queries": [],
                "edited_queries": [],
                "combine": "none",
                "reason": reason,
            },
            "extra": {
                "mode": mode,
                "edit_type": edit_scope,
                "selection_policy": selection_policy,
                "m": len(applicable),
                "n_shots": len(all_shots),
                "source_tasks": _source_task_counts(logical_edits),
                "shot_edits": shot_edits,
                "untouched_shots": untouched,
            },
            "author": AUTHOR,
        }
        if mode == "persistent_object_edit":
            sample["edit"]["extra"]["object_edits"] = object_edits
            sample["edit"]["extra"]["n_object_edits"] = len(object_edits)
            sample["edit"]["extra"]["continuity_policy"] = (
                "Each object edit starts at start_shot and remains active in every later applicable shot "
                "where that named object appears; edits do not transfer to other objects."
            )
        errors.extend(_validate_sample(sample))
        out.append(sample)

    if errors:
        raise ValueError("T9 validation failed:\n" + "\n".join(errors))
    return out


def _task_stats(samples: list[dict]) -> dict:
    task_counter = Counter()
    mode_counter = Counter()
    task_by_mode = {}
    video_counter = Counter()
    shot_span = Counter()
    m_dist = Counter()
    for sample in samples:
        mode = sample["edit"]["extra"].get("mode", "independent_per_shot")
        mode_counter[mode] += 1
        task_by_mode.setdefault(mode, Counter())
        video_counter[sample["video_id"]] += 1
        m = len(sample["edit"]["applicable_shots"])
        shot_span[str(m)] += 1
        m_dist[str(m)] += 1
        logical_edits = sample["edit"]["extra"].get("object_edits") or sample["edit"]["extra"]["shot_edits"]
        for edit in logical_edits:
            task_counter[edit["source_task"]] += 1
            task_by_mode[mode][edit["source_task"]] += 1
    return {
        "count": len(samples),
        "edit_type": {"shot_conditioned_composite": len(samples)},
        "modes": dict(sorted(mode_counter.items())),
        "source_task_ops": dict(sorted(task_counter.items())),
        "source_task_ops_by_mode": {
            mode: dict(sorted(counter.items())) for mode, counter in sorted(task_by_mode.items())
        },
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
