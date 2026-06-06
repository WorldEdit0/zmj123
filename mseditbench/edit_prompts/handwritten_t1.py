"""Hand-written edit prompts authored by Claude.

Each entry is a (instruction, target_phrase) tuple typed by hand for that
specific (video, edit) context. Not template-filled.

Loaded by build_v1_2.py which inherits all structural fields (sample_id,
applicable_shots, target_entity, etc.) from v1 and only
substitutes the two strings.

Coverage note is historical; current production prompts are under
`runs/edit_prompts_v2_10s/`.
"""

HAND_T1 = {
# ─── 00000 kitchen_morning_dialogue (C1=woman in red sweater, C2=man in navy shirt) ─
"00000_T1_0000": ("Replace the young woman in the red knit sweater with a bride in a flowing white wedding gown and long veil, in every shot she appears.",
                  "a bride in a white wedding gown with long veil"),
"00000_T1_0001": ("Throughout the kitchen scene, recast the young woman in the red knit sweater as a clown in a polka-dot suit with rainbow hair and white face paint.",
                  "a clown with rainbow hair, white face paint, and a polka-dot suit"),
"00000_T1_0002": ("Substitute the older man in the navy blue shirt with a chrome humanoid robot whose eyes glow blue, in every shot of the video.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00000_T1_0003": ("Make the older man in the navy blue shirt appear as a clown with rainbow hair, white face paint and a polka-dot suit, throughout the video.",
                  "a clown with rainbow hair, white face paint, and a polka-dot suit"),
# ─── 00001 office_meeting_quiet (C1=man in grey suit, C2=woman in white blouse) ─
"00001_T1_0004": ("Across every shot of the meeting, render the man in the grey suit jacket as a chrome humanoid robot with glowing blue eyes.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00001_T1_0005": ("Recast the man in the grey suit jacket as a knight in shining medieval armour with a red plume, in every shot.",
                  "a knight in shining medieval armor with a red plume"),
"00001_T1_0006": ("Throughout the meeting, replace the woman in the white blouse with a knight in shining medieval armour with a red plume.",
                  "a knight in shining medieval armor with a red plume"),
"00001_T1_0007": ("Have the woman in the white blouse appear instead as a chrome humanoid robot with glowing blue eyes, in every shot.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
# ─── 00002 street_cafe_evening (C1=woman with red curly hair, C2=man with short beard) ─
"00002_T1_0008": ("Replace the woman in the black leather jacket with a bride in a flowing white wedding gown and long veil, throughout the cafe scene.",
                  "a bride in a white wedding gown with long veil"),
"00002_T1_0009": ("In every shot, render the woman in the black leather jacket as a chrome humanoid robot with glowing blue eyes.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00002_T1_0010": ("Substitute the bearded man in the beige cardigan for an old man with a long white beard wearing a brown robe, in all shots.",
                  "an old man with a long white beard, wearing a brown robe"),
"00002_T1_0011": ("Across the entire cafe scene, recast the bearded man in the beige cardigan as a knight in shining medieval armour with a red plume.",
                  "a knight in shining medieval armor with a red plume"),
# ─── 00003 bedroom_morning_solo (C1=young man in white t-shirt) ─
"00003_T1_0012": ("Replace the young man in the white t-shirt with a knight in shining medieval armour with a red plume, throughout the bedroom scene.",
                  "a knight in shining medieval armor with a red plume"),
"00003_T1_0013": ("Throughout every shot, render the young man in the white t-shirt as a clown with rainbow hair, white face paint and a polka-dot suit.",
                  "a clown with rainbow hair, white face paint, and a polka-dot suit"),
# ─── 00004 library_studying_solo (C1=girl in green hoodie) ─
"00004_T1_0014": ("Recast the girl in the green hoodie as a young child with curly black hair in a school uniform, in every shot of the library.",
                  "a young child about ten years old with curly black hair, wearing a school uniform"),
"00004_T1_0015": ("Replace the girl in the green hoodie with a knight in shining medieval armour with a red plume, throughout the video.",
                  "a knight in shining medieval armor with a red plume"),
# ─── 00005 park_jogging_evening (C1=athletic woman in light blue running jacket) ─
"00005_T1_0016": ("Throughout the jogging sequence, replace the athletic woman in the light blue running jacket with an astronaut in a full white space suit and lowered visor.",
                  "an astronaut in a full white space suit with the visor down"),
"00005_T1_0017": ("Make the athletic woman in the light blue running jacket appear as a pirate captain in a tricorn hat, eye patch and red coat, in every shot.",
                  "a pirate captain with a tricorn hat, eye patch, and red coat"),
# ─── 00006 kitchen_cooking_solo (C1=man in navy apron) ─
"00006_T1_0018": ("Substitute the bearded man in the navy apron for a clown in a polka-dot suit with rainbow hair and white face paint, throughout the cooking scene.",
                  "a clown with rainbow hair, white face paint, and a polka-dot suit"),
"00006_T1_0019": ("Across all shots, recast the bearded man in the navy apron as a chrome humanoid robot with glowing blue eyes.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
# ─── 00007 garage_repair_solo (C1=mechanic woman in blue overalls) ─
"00007_T1_0020": ("Replace the mechanic in the blue overalls with a knight in shining medieval armour with a red plume, in every shot of the garage.",
                  "a knight in shining medieval armor with a red plume"),
"00007_T1_0021": ("Throughout the repair scene, render the mechanic in the blue overalls as a pirate captain in a tricorn hat, eye patch and red coat.",
                  "a pirate captain with a tricorn hat, eye patch, and red coat"),
# ─── 00008 restaurant_waiter_dinner (C1=waiter in black vest, C2=elderly woman in purple shawl) ─
"00008_T1_0022": ("Recast the waiter in the black vest as a knight in shining medieval armour with a red plume, in every shot of the restaurant.",
                  "a knight in shining medieval armor with a red plume"),
"00008_T1_0023": ("Replace the waiter in the black vest with an astronaut in a full white space suit and lowered visor, throughout the scene.",
                  "an astronaut in a full white space suit with the visor down"),
"00008_T1_0024": ("Throughout the dinner scene, render the elderly woman in the purple shawl as an astronaut in a full white space suit with lowered visor.",
                  "an astronaut in a full white space suit with the visor down"),
"00008_T1_0025": ("In every shot, recast the elderly woman in the purple shawl as a young child with curly black hair in a school uniform.",
                  "a young child about ten years old with curly black hair, wearing a school uniform"),
# ─── 00009 beach_walking_couple (C1=woman in yellow dress, C2=young man in white linen shirt) ─
"00009_T1_0026": ("Replace the young woman in the yellow summer dress with a bride in a flowing white wedding gown and long veil, throughout the beach walk.",
                  "a bride in a white wedding gown with long veil"),
"00009_T1_0027": ("Throughout the beach scene, recast the young woman in the yellow summer dress as a chrome humanoid robot with glowing blue eyes.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00009_T1_0028": ("Have the young man in the white linen shirt appear as an astronaut in a full white space suit with lowered visor, in every shot.",
                  "an astronaut in a full white space suit with the visor down"),
"00009_T1_0029": ("Substitute the young man in the white linen shirt for a clown in a polka-dot suit with rainbow hair and white face paint, throughout the beach walk.",
                  "a clown with rainbow hair, white face paint, and a polka-dot suit"),
# ─── 00010 rooftop_phonecall_night (C1=man in charcoal grey overcoat) ─
"00010_T1_0030": ("Across every shot, replace the man in the charcoal grey overcoat with a knight in shining medieval armour with a red plume.",
                  "a knight in shining medieval armor with a red plume"),
"00010_T1_0031": ("Throughout the rooftop phone call, render the man in the charcoal grey overcoat as an old man with a long white beard wearing a brown robe.",
                  "an old man with a long white beard, wearing a brown robe"),
# ─── 00011 subway_commute_morning (C1=woman in tan trench coat) ─
"00011_T1_0032": ("Replace the woman in the tan trench coat with a young child with curly black hair in a school uniform, throughout the subway scene.",
                  "a young child about ten years old with curly black hair, wearing a school uniform"),
"00011_T1_0033": ("In every shot of the subway, recast the woman in the tan trench coat as an astronaut in a full white space suit with lowered visor.",
                  "an astronaut in a full white space suit with the visor down"),
# ─── 00012 forest_hiking_solo (C1=hiker with grey beanie, orange backpack) ─
"00012_T1_0034": ("Throughout the hike, replace the hiker in the grey beanie with the orange backpack with a chrome humanoid robot with glowing blue eyes.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00012_T1_0035": ("Across all shots, recast the hiker in the grey beanie and orange backpack as a knight in shining medieval armour with a red plume.",
                  "a knight in shining medieval armor with a red plume"),
# ─── 00013 bookstore_browsing_couple (C1=woman with pink hair in denim, C2=man in maroon sweater) ─
"00013_T1_0036": ("Replace the woman in the denim jacket with the pink hair with an old man with a long white beard wearing a brown robe, throughout the bookstore.",
                  "an old man with a long white beard, wearing a brown robe"),
"00013_T1_0037": ("In every shot, render the woman in the denim jacket as a pirate captain in a tricorn hat, eye patch and red coat.",
                  "a pirate captain with a tricorn hat, eye patch, and red coat"),
"00013_T1_0038": ("Throughout the bookstore scene, replace the man in the maroon sweater with a young child with curly black hair in a school uniform.",
                  "a young child about ten years old with curly black hair, wearing a school uniform"),
"00013_T1_0039": ("Recast the man in the maroon sweater as an astronaut in a full white space suit with lowered visor, in every shot.",
                  "an astronaut in a full white space suit with the visor down"),
# ─── 00014 playground_kid_solo (C1=girl in pink jacket with ginger pigtails) ─
"00014_T1_0040": ("Replace the small girl in the pink jacket with a chrome humanoid robot with glowing blue eyes, in every shot of the playground.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00014_T1_0041": ("Throughout the playground scene, recast the small girl in the pink jacket as a pirate captain in a tricorn hat, eye patch and red coat.",
                  "a pirate captain with a tricorn hat, eye patch, and red coat"),
# ─── 00015 train_station_farewell (C1=older woman in green coat, C2=man in dark wool coat) ─
"00015_T1_0042": ("Replace the older woman in the long green coat with a young child with curly black hair in a school uniform, throughout the train station scene.",
                  "a young child about ten years old with curly black hair, wearing a school uniform"),
"00015_T1_0043": ("In every shot, recast the older woman in the long green coat as a chrome humanoid robot with glowing blue eyes.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00015_T1_0044": ("Substitute the man in the dark wool coat for an astronaut in a full white space suit with lowered visor, throughout the farewell scene.",
                  "an astronaut in a full white space suit with the visor down"),
"00015_T1_0045": ("Throughout the train platform sequence, render the man in the dark wool coat as an old man with a long white beard wearing a brown robe.",
                  "an old man with a long white beard, wearing a brown robe"),
# ─── 00016 art_studio_painting_solo (C1=elderly woman in paint-stained apron) ─
"00016_T1_0046": ("Replace the elderly woman in the paint-stained grey apron with a clown in a polka-dot suit with rainbow hair and white face paint, throughout the art studio scene.",
                  "a clown with rainbow hair, white face paint, and a polka-dot suit"),
"00016_T1_0047": ("In every shot of the studio, recast the elderly woman in the paint-stained apron as a chrome humanoid robot with glowing blue eyes.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
# ─── 00017 gym_workout_solo (C1=muscular man in black tank top) ─
"00017_T1_0048": ("Throughout the gym scene, replace the muscular man in the black tank top with an old man with a long white beard wearing a brown robe.",
                  "an old man with a long white beard, wearing a brown robe"),
"00017_T1_0049": ("In every shot, render the muscular man in the black tank top as a young child with curly black hair in a school uniform.",
                  "a young child about ten years old with curly black hair, wearing a school uniform"),
# ─── 00018 garden_planting_solo (C1=older man in straw hat with grey ponytail) ─
"00018_T1_0050": ("Recast the older man in the straw hat as a chrome humanoid robot with glowing blue eyes, throughout the gardening scene.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00018_T1_0051": ("Replace the older man in the straw hat with a bride in a flowing white wedding gown and long veil, in every shot of the garden.",
                  "a bride in a white wedding gown with long veil"),
# ─── 00019 studio_recording_solo (C1=young woman with purple hair) ─
"00019_T1_0052": ("Replace the young woman with the shoulder-length purple hair with a knight in shining medieval armour with a red plume, throughout the recording studio.",
                  "a knight in shining medieval armor with a red plume"),
"00019_T1_0053": ("Throughout the recording session, render the young woman with the purple hair as a pirate captain in a tricorn hat, eye patch and red coat.",
                  "a pirate captain with a tricorn hat, eye patch, and red coat"),
# ─── 00020 classroom_teacher_lesson (C1=female teacher in cream blouse) ─
"00020_T1_0054": ("Replace the female teacher in the cream blouse with a chrome humanoid robot with glowing blue eyes, throughout the classroom scene.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00020_T1_0055": ("Across every shot, recast the female teacher in the cream blouse as a pirate captain in a tricorn hat, eye patch and red coat.",
                  "a pirate captain with a tricorn hat, eye patch, and red coat"),
# ─── 00021 hospital_corridor_walk (C1=female doctor, C2=concerned middle-aged woman) ─
"00021_T1_0056": ("Throughout the hospital corridor scene, replace the female doctor in the white coat with a knight in shining medieval armour with a red plume.",
                  "a knight in shining medieval armor with a red plume"),
"00021_T1_0057": ("Recast the female doctor in the white coat as an old man with a long white beard wearing a brown robe, in every shot.",
                  "an old man with a long white beard, wearing a brown robe"),
"00021_T1_0058": ("In every shot, replace the middle-aged woman in the beige cardigan with a young child with curly black hair in a school uniform.",
                  "a young child about ten years old with curly black hair, wearing a school uniform"),
"00021_T1_0059": ("Throughout the corridor scene, render the middle-aged woman in the beige cardigan as a chrome humanoid robot with glowing blue eyes.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
# ─── 00022 cafe_writing_solo (C1=man in green sweater with round glasses) ─
"00022_T1_0060": ("Replace the man in the forest-green sweater with a clown in a polka-dot suit with rainbow hair and white face paint, throughout the cafe scene.",
                  "a clown with rainbow hair, white face paint, and a polka-dot suit"),
"00022_T1_0061": ("In every shot, recast the man in the forest-green sweater as an astronaut in a full white space suit with lowered visor.",
                  "an astronaut in a full white space suit with the visor down"),
# ─── 00023 alley_cat_observation (C1=young man in grey hoodie) ─
"00023_T1_0062": ("Replace the young man in the faded grey hoodie with a knight in shining medieval armour with a red plume, throughout the alley scene.",
                  "a knight in shining medieval armor with a red plume"),
"00023_T1_0063": ("Throughout the alley sequence, render the young man in the grey hoodie as a chrome humanoid robot with glowing blue eyes.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
# ─── 00024 office_late_night_solo (C1=tired woman in white shirt) ─
"00024_T1_0064": ("Throughout the late-night office scene, replace the tired woman in the wrinkled white shirt with a chrome humanoid robot with glowing blue eyes.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00024_T1_0065": ("In every shot, recast the tired woman in the wrinkled white shirt as a knight in shining medieval armour with a red plume.",
                  "a knight in shining medieval armor with a red plume"),
# ─── 00025 barbershop_haircut (C1=barber with handlebar mustache, C2=young man with shaggy hair) ─
"00025_T1_0066": ("Replace the barber with the handlebar mustache with a pirate captain in a tricorn hat, eye patch and red coat, throughout the barbershop scene.",
                  "a pirate captain with a tricorn hat, eye patch, and red coat"),
"00025_T1_0067": ("In every shot, render the barber with the handlebar mustache as an old man with a long white beard wearing a brown robe.",
                  "an old man with a long white beard, wearing a brown robe"),
"00025_T1_0068": ("Throughout the haircut, recast the young man with the shaggy brown hair as a chrome humanoid robot with glowing blue eyes.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00025_T1_0069": ("Replace the young man with the shaggy brown hair with a young child with curly black hair in a school uniform, in every shot of the barbershop.",
                  "a young child about ten years old with curly black hair, wearing a school uniform"),
# ─── 00026 rainy_street_umbrella (C1=woman in black raincoat with red umbrella) ─
"00026_T1_0070": ("Replace the woman in the long black raincoat with a chrome humanoid robot with glowing blue eyes, throughout the rainy street scene.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00026_T1_0071": ("Recast the woman in the long black raincoat as an astronaut in a full white space suit with lowered visor, in every shot.",
                  "an astronaut in a full white space suit with the visor down"),
# ─── 00027 music_lesson_child (C1=older man in tweed vest, C2=small girl in yellow dress) ─
"00027_T1_0072": ("Throughout the piano lesson, replace the older man in the brown tweed vest with a knight in shining medieval armour with a red plume.",
                  "a knight in shining medieval armor with a red plume"),
"00027_T1_0073": ("In every shot of the music lesson, recast the older man in the brown tweed vest as a pirate captain in a tricorn hat, eye patch and red coat.",
                  "a pirate captain with a tricorn hat, eye patch, and red coat"),
"00027_T1_0074": ("Replace the small girl in the pale yellow dress with an astronaut in a full white space suit with lowered visor, throughout the music lesson.",
                  "an astronaut in a full white space suit with the visor down"),
"00027_T1_0075": ("In every shot, render the small girl in the pale yellow dress as a clown in a polka-dot suit with rainbow hair and white face paint.",
                  "a clown with rainbow hair, white face paint, and a polka-dot suit"),
# ─── 00028 beach_storm_dog (C1=man in red windbreaker, C2=golden retriever) ─
"00028_T1_0076": ("Throughout the stormy beach scene, replace the man in the red windbreaker with a chrome humanoid robot with glowing blue eyes.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00028_T1_0077": ("In every shot, recast the man in the red windbreaker as a knight in shining medieval armour with a red plume.",
                  "a knight in shining medieval armor with a red plume"),
"00028_T1_0078": ("Replace the golden retriever with a chrome humanoid robot with glowing blue eyes, throughout the beach storm scene.",
                  "a robot with a chrome humanoid body and glowing blue eyes"),
"00028_T1_0079": ("In every shot, recast the golden retriever as a knight in shining medieval armour with a red plume.",
                  "a knight in shining medieval armor with a red plume"),
# ─── 00029 rooftop_morning_yoga (C1=woman in light grey yoga clothes with auburn ponytail) ─
"00029_T1_0080": ("Replace the woman in the light grey yoga clothes with an astronaut in a full white space suit with lowered visor, throughout the rooftop yoga scene.",
                  "an astronaut in a full white space suit with the visor down"),
"00029_T1_0081": ("Throughout the sunrise yoga, recast the woman in the light grey yoga clothes as a clown in a polka-dot suit with rainbow hair and white face paint.",
                  "a clown with rainbow hair, white face paint, and a polka-dot suit"),
}
