# MSEdit-Bench Pilot — Shot Detection Validation Report

Total videos: **30**

## Summary

- ✅ Exact match (actual == expected): **30 / 30** (100%)
- ⚠️  Off-by-one: **0** (0%)
- ❌ Off by more / failed: **0** + **0 errors**
- TransNetV2 ran on **30 / 30** videos
- TransNetV2 ↔ PySceneDetect count agreement: **28 / 30**
- TransNetV2 ↔ PySceneDetect full agreement (count + boundaries within 0.25s): **28 / 30**

## Recommendations

- ✅ Hit rate 100% >= 85%. SAFE TO SCALE: extend prompt set to 150 videos.

## Distributions

Expected shots: `{3: 6, 4: 16, 5: 8}`
Actual shots: `{3: 6, 4: 16, 5: 8}`
Diff (actual − expected): `{'0': 30}`

## Per-category hit rate

| Category | Total | Exact | Hit rate |
|---|---|---|---|
| `dialogue_2person_indoor` | 5 | 5 | 100% |
| `dialogue_2person_outdoor` | 2 | 2 | 100% |
| `daily_life_solo` | 2 | 2 | 100% |
| `action_solo_outdoor` | 3 | 3 | 100% |
| `action_solo_indoor` | 5 | 5 | 100% |
| `outdoor_couple` | 1 | 1 | 100% |
| `daily_life_solo_outdoor` | 2 | 2 | 100% |
| `daily_life_solo_indoor` | 3 | 3 | 100% |
| `outdoor_solo_nature` | 1 | 1 | 100% |
| `daily_life_couple_indoor` | 1 | 1 | 100% |
| `dialogue_groupchild_indoor` | 1 | 1 | 100% |
| `outdoor_solo_observation` | 2 | 2 | 100% |
| `action_2person_indoor` | 1 | 1 | 100% |
| `outdoor_solo_dynamic` | 1 | 1 | 100% |

## Per-video records

| video_id | scene_id | category | expected | actual (consensus) | TN | PS | TN↔PS agree | match | note |
|---|---|---|---|---|---|---|---|---|---|
| `00000` | `kitchen_morning_dialogue` | `dialogue_2person_indoor` | 3 | 3 | 3 | 3 | ✓ | ✅ |  |
| `00001` | `office_meeting_quiet` | `dialogue_2person_indoor` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00002` | `street_cafe_evening` | `dialogue_2person_outdoor` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00003` | `bedroom_morning_solo` | `daily_life_solo` | 3 | 3 | 3 | 3 | ✓ | ✅ |  |
| `00004` | `library_studying_solo` | `daily_life_solo` | 3 | 3 | 3 | 3 | ✓ | ✅ |  |
| `00005` | `park_jogging_evening` | `action_solo_outdoor` | 5 | 5 | 5 | 5 | ✓ | ✅ |  |
| `00006` | `kitchen_cooking_solo` | `action_solo_indoor` | 5 | 5 | 5 | 5 | ✓ | ✅ |  |
| `00007` | `garage_repair_solo` | `action_solo_indoor` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00008` | `restaurant_waiter_dinner` | `dialogue_2person_indoor` | 5 | 5 | 5 | 5 | ✓ | ✅ |  |
| `00009` | `beach_walking_couple` | `outdoor_couple` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00010` | `rooftop_phonecall_night` | `daily_life_solo_outdoor` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00011` | `subway_commute_morning` | `daily_life_solo_indoor` | 3 | 3 | 3 | 3 | ✓ | ✅ |  |
| `00012` | `forest_hiking_solo` | `outdoor_solo_nature` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00013` | `bookstore_browsing_couple` | `daily_life_couple_indoor` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00014` | `playground_kid_solo` | `daily_life_solo_outdoor` | 4 | 4 | 4 | 6 | ✗ | ✅ |  |
| `00015` | `train_station_farewell` | `dialogue_2person_outdoor` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00016` | `art_studio_painting_solo` | `action_solo_indoor` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00017` | `gym_workout_solo` | `action_solo_indoor` | 5 | 5 | 5 | 5 | ✓ | ✅ |  |
| `00018` | `garden_planting_solo` | `action_solo_outdoor` | 5 | 5 | 5 | 5 | ✓ | ✅ |  |
| `00019` | `studio_recording_solo` | `action_solo_indoor` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00020` | `classroom_teacher_lesson` | `dialogue_groupchild_indoor` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00021` | `hospital_corridor_walk` | `dialogue_2person_indoor` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00022` | `cafe_writing_solo` | `daily_life_solo_indoor` | 3 | 3 | 3 | 3 | ✓ | ✅ |  |
| `00023` | `alley_cat_observation` | `outdoor_solo_observation` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00024` | `office_late_night_solo` | `daily_life_solo_indoor` | 5 | 5 | 5 | 5 | ✓ | ✅ |  |
| `00025` | `barbershop_haircut` | `action_2person_indoor` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00026` | `rainy_street_umbrella` | `outdoor_solo_observation` | 3 | 3 | 3 | 3 | ✓ | ✅ |  |
| `00027` | `music_lesson_child` | `dialogue_2person_indoor` | 4 | 4 | 4 | 4 | ✓ | ✅ |  |
| `00028` | `beach_storm_dog` | `outdoor_solo_dynamic` | 5 | 5 | 5 | 2 | ✗ | ✅ |  |
| `00029` | `rooftop_morning_yoga` | `action_solo_outdoor` | 5 | 5 | 5 | 5 | ✓ | ✅ |  |
