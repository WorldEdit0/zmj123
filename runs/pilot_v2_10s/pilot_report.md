# MSEdit-Bench Pilot — Shot Detection Validation Report

Total videos: **30**

## Summary

- ✅ Exact match (actual == expected): **30 / 30** (100%)
- ⚠️  Off-by-one: **0** (0%)
- ❌ Off by more / failed: **0** + **0 errors**
- TransNetV2 ran on **30 / 30** videos
- TransNetV2 ↔ PySceneDetect count agreement: **25 / 30**
- TransNetV2 ↔ PySceneDetect full agreement (count + boundaries within 0.25s): **25 / 30**

## Recommendations

- ✅ Hit rate 100% >= 85%. SAFE TO SCALE: extend prompt set to 150 videos.

## Distributions

Expected shots: `{3: 6, 4: 18, 5: 6}`
Actual shots: `{3: 6, 4: 18, 5: 6}`
Diff (actual − expected): `{'0': 30}`

## Per-category hit rate

| Category | Total | Exact | Hit rate |
|---|---|---|---|
| `service_indoor_solo` | 4 | 4 | 100% |
| `craft_indoor_solo` | 4 | 4 | 100% |
| `performance_indoor_2person` | 2 | 2 | 100% |
| `lifestyle_indoor_2person` | 1 | 1 | 100% |
| `lifestyle_special_solo` | 1 | 1 | 100% |
| `sport_outdoor_2person` | 1 | 1 | 100% |
| `performance_indoor_solo` | 1 | 1 | 100% |
| `sport_outdoor_solo` | 2 | 2 | 100% |
| `service_indoor_2person` | 3 | 3 | 100% |
| `work_outdoor_solo` | 1 | 1 | 100% |
| `sport_indoor_2person` | 1 | 1 | 100% |
| `lifestyle_outdoor_solo` | 2 | 2 | 100% |
| `service_outdoor_2person` | 1 | 1 | 100% |
| `performance_outdoor_2person` | 1 | 1 | 100% |
| `work_indoor_solo` | 1 | 1 | 100% |
| `lifestyle_outdoor_3person` | 2 | 2 | 100% |
| `lifestyle_indoor_3person` | 1 | 1 | 100% |
| `drama_indoor_3person` | 1 | 1 | 100% |

## Per-video records

| video_id | scene_id | category | expected | actual (consensus) | TN | PS | TN↔PS agree | match | note |
|---|---|---|---|---|---|---|---|---|---|
| `00000` | `coffee_barista_latte_art` | `service_indoor_solo` | 3 | 3 | 3 | 3 | ✓ | ✅ |  |
| `00001` | `potter_centering_clay` | `craft_indoor_solo` | 3 | 3 | 3 | 3 | ✓ | ✅ |  |
| `00002` | `florist_bouquet_wrap` | `service_indoor_solo` | 3 | 3 | 3 | 3 | ✓ | ✅ |  |
| `00003` | `magician_card_reveal` | `performance_indoor_2person` | 3 | 3 | 3 | 3 | ✓ | ✅ |  |
| `00004` | `tarot_card_reading` | `lifestyle_indoor_2person` | 3 | 3 | 3 | 3 | ✓ | ✅ |  |
| `00005` | `astronaut_zero_gravity_drink` | `lifestyle_special_solo` | 3 | 3 | 3 | 3 | ✓ | ✅ |  |
| `00006` | `skater_kickflip_park` | `sport_outdoor_2person` | 4 | 4 | 3 | 3 | ✓ | ✅ |  |
| `00007` | `dj_concert_set` | `performance_indoor_solo` | 4 | 4 | 2 | 6 | ✗ | ✅ |  |
| `00008` | `surfer_dawn_patrol` | `sport_outdoor_solo` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00009` | `snowboarder_mountain_run` | `sport_outdoor_solo` | 4 | 4 | 4 | 2 | ✗ | ✅ |  |
| `00010` | `tattoo_artist_session` | `service_indoor_2person` | 4 | 4 | 4 | 3 | ✗ | ✅ |  |
| `00011` | `glass_blower_vase` | `craft_indoor_solo` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00012` | `calligrapher_brush_stroke` | `craft_indoor_solo` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00013` | `locksmith_picking_lock` | `work_outdoor_solo` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00014` | `veterinarian_puppy_checkup` | `service_indoor_2person` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00015` | `watch_repair_workshop` | `craft_indoor_solo` | 4 | 4 | 4 | 3 | ✗ | ✅ |  |
| `00016` | `chef_dessert_plating` | `service_indoor_solo` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00017` | `yoga_partner_stretch` | `sport_indoor_2person` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00018` | `dog_grooming_salon` | `service_indoor_solo` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00019` | `backyard_bbq_grill` | `lifestyle_outdoor_solo` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00020` | `fishing_on_dock` | `lifestyle_outdoor_solo` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00021` | `acupuncture_session` | `service_indoor_2person` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00022` | `ice_cream_truck` | `service_outdoor_2person` | 4 | 4 | 4 | 6 | ✗ | ✅ |  |
| `00023` | `busker_subway_musician` | `performance_outdoor_2person` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00024` | `car_mechanic_engine_swap` | `work_indoor_solo` | 5 | 5 | 5 | 5 | ✓ | ✅ |  |
| `00025` | `hot_air_balloon_launch` | `lifestyle_outdoor_3person` | 5 | 5 | 5 | 5 | ✓ | ✅ |  |
| `00026` | `wedding_dress_fitting` | `lifestyle_indoor_3person` | 5 | 5 | 5 | 5 | ✓ | ✅ |  |
| `00027` | `courtroom_verdict` | `drama_indoor_3person` | 5 | 5 | 5 | 5 | ✓ | ✅ |  |
| `00028` | `campfire_ghost_story` | `lifestyle_outdoor_3person` | 5 | 5 | 5 | 5 | ✓ | ✅ |  |
| `00029` | `bartender_cocktail_show` | `performance_indoor_2person` | 5 | 5 | 5 | 5 | ✓ | ✅ |  |

## Contact sheets

### 00000 (coffee_barista_latte_art)
![00000](contact_sheets/00000_contact.jpg)

### 00001 (potter_centering_clay)
![00001](contact_sheets/00001_contact.jpg)

### 00002 (florist_bouquet_wrap)
![00002](contact_sheets/00002_contact.jpg)

### 00003 (magician_card_reveal)
![00003](contact_sheets/00003_contact.jpg)

### 00004 (tarot_card_reading)
![00004](contact_sheets/00004_contact.jpg)

### 00005 (astronaut_zero_gravity_drink)
![00005](contact_sheets/00005_contact.jpg)

### 00006 (skater_kickflip_park)
![00006](contact_sheets/00006_contact.jpg)

### 00007 (dj_concert_set)
![00007](contact_sheets/00007_contact.jpg)

### 00008 (surfer_dawn_patrol)
![00008](contact_sheets/00008_contact.jpg)

### 00009 (snowboarder_mountain_run)
![00009](contact_sheets/00009_contact.jpg)

### 00010 (tattoo_artist_session)
![00010](contact_sheets/00010_contact.jpg)

### 00011 (glass_blower_vase)
![00011](contact_sheets/00011_contact.jpg)

### 00012 (calligrapher_brush_stroke)
![00012](contact_sheets/00012_contact.jpg)

### 00013 (locksmith_picking_lock)
![00013](contact_sheets/00013_contact.jpg)

### 00014 (veterinarian_puppy_checkup)
![00014](contact_sheets/00014_contact.jpg)

### 00015 (watch_repair_workshop)
![00015](contact_sheets/00015_contact.jpg)

### 00016 (chef_dessert_plating)
![00016](contact_sheets/00016_contact.jpg)

### 00017 (yoga_partner_stretch)
![00017](contact_sheets/00017_contact.jpg)

### 00018 (dog_grooming_salon)
![00018](contact_sheets/00018_contact.jpg)

### 00019 (backyard_bbq_grill)
![00019](contact_sheets/00019_contact.jpg)

### 00020 (fishing_on_dock)
![00020](contact_sheets/00020_contact.jpg)

### 00021 (acupuncture_session)
![00021](contact_sheets/00021_contact.jpg)

### 00022 (ice_cream_truck)
![00022](contact_sheets/00022_contact.jpg)

### 00023 (busker_subway_musician)
![00023](contact_sheets/00023_contact.jpg)

### 00024 (car_mechanic_engine_swap)
![00024](contact_sheets/00024_contact.jpg)

### 00025 (hot_air_balloon_launch)
![00025](contact_sheets/00025_contact.jpg)

### 00026 (wedding_dress_fitting)
![00026](contact_sheets/00026_contact.jpg)

### 00027 (courtroom_verdict)
![00027](contact_sheets/00027_contact.jpg)

### 00028 (campfire_ghost_story)
![00028](contact_sheets/00028_contact.jpg)

### 00029 (bartender_cocktail_show)
![00029](contact_sheets/00029_contact.jpg)
