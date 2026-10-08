# Demo — Touch Grass Garden

Real, unedited output from running the project on an 8 GB RAM, CPU-only
Windows laptop. No network calls at any point during these runs.

## 1. Health check

```
> uv run touchgrass doctor

Touch Grass Garden 0.1.0
  [ok] llama-cpp-python installed
  [ok] model found: qwen2.5-1.5b-instruct-q4_k_m.gguf (1117 MB)
  [ok] frost dates + crop rules bundled (offline data)

Everything present - you can go touch grass.
```

## 2. Weekly briefing (deterministic plan + local Qwen2.5-1.5B)

```
> touchgrass brief denver --date 2026-03-15

==========================================================================
  TOUCH GRASS GARDEN - week of Sunday, March 15, 2026
  Denver, CO (zone 5b)
==========================================================================
  Next last-frost:  May 05   First fall-frost: Oct 05   Season: 153 days
--------------------------------------------------------------------------
  DO THIS WEEK (9 jobs, in priority order):
  + Start indoors Peppers                                Mar 10 (5 day(s) ago)
  + Start indoors Eggplant                               Mar 10 (5 day(s) ago)
  + Start indoors Broccoli & Cauliflower                 Mar 10 (5 day(s) ago)
  + Start indoors Cabbage & Brussels Sprouts             Mar 10 (5 day(s) ago)
  + Start indoors Roses, Coneflower & Pollinator Perennials Mar 10 (5 day(s) ago)
  + Start indoors Tomatoes                               Mar 24 (in 9 days)
  + Start indoors Sweet Potatoes                         Mar 24 (in 9 days)
  + Start indoors Basil                                  Mar 24 (in 9 days)
  + Start indoors Kale & Collards                        Mar 24 (in 9 days)
--------------------------------------------------------------------------
  ON DECK (next 45 days):
  + Start indoors Okra                                   Apr 07 (in 23 days)
  + Start indoors Lettuce & Salad Greens                 Apr 07 (in 23 days)
  + Direct sow    Spinach                                Apr 07 (in 23 days)
  + Direct sow    Radishes                               Apr 07 (in 23 days)
  + Direct sow    Turnips & Rutabaga                     Apr 07 (in 23 days)
--------------------------------------------------------------------------
  ROUGH HARVEST FORECASTS:
    ~ Tomatoes: ~Jul 28 from the earliest safe planting (May 19)
    ~ Peppers: ~Aug 02 from the earliest safe planting (May 19)
    ~ Eggplant: ~Aug 09 from the earliest safe planting (May 26)
    ~ Cucumbers: ~Jul 13 from the earliest safe planting (May 19)
--------------------------------------------------------------------------
  Data: bundled frost normals + crop rules (offline, no API calls).
  Your yard beats averages: check soil, not just the calendar.
==========================================================================

  WEEKLY BRIEFING (local Qwen2.5-1.5B, running on this machine)

  Exciting spring gardening season ahead! Ready to start those seedlings
  outdoors and get those vegetables growing strong! Here's your weekly
  garden briefing:
  Top Priority: Outdoor Seedling Start
  Start your indoor seedlings on March 10 and continue until your last
  frost date of May 5. This ensures your seedlings have enough time to
  grow strong and healthy before the outdoor temperature drops. For
  instance, start your peppers now and keep them in a sunny spot.
  Top Priority: Direct Sowing
  Direct sow your spinach, radishes, turnips, rutabagas, and other root
  veggies around April 7. This method is perfect for those impatient
  gardeners who want to see their harvest quickly.
  Top Priority: Sweet Potatoes
  Sweet potatoes are another great choice for direct sowing. They
  require a bit more patience, typically ready around April 7, but the
  results are well worth the wait.
  Important to Watch: Keep an eye on your plants for any signs of pests
  or disease. With the warmer weather, pests like aphids and cucumber
  beetles might start to appear. Regularly inspect your plants and clean
  up any debris to prevent these issues.

  [qwen2.5-1.5b-instruct-q4_k_m.gguf loaded in 7.3s, generated at 6.8 tok/s, offline]
```

Note the split of responsibilities: every date in the plan comes from
deterministic frost math (unit-tested); the model only writes the prose
around verified facts.

## 3. Offline Q&A

```
> touchgrass ask denver --date 2026-10-06 "is it too late to plant garlic here?"

No, it is not too late to plant garlic. Garlic can be planted any time
after the first fall frost date, which is October 5th in Denver, CO
(zone 5b). You can continue to plant garlic until the soil temperature
is consistently below 50 degrees F (10 degrees C), typically occurring
around late October. Go outside and check the soil temperature for
accurate timing.

[qwen2.5-1.5b-instruct-q4_k_m.gguf, 6.5 tok/s, offline]
```

## 4. In-season fall run (Portland, OR)

```
> touchgrass brief portland --date 2026-10-06

  DO THIS WEEK (1 jobs, in priority order):
  * Plant         Tulips & Daffodils                     Oct 04 (2 day(s) ago)

  ON DECK (next 45 days):
  + Plant         Garlic (fall planting)                 Oct 18 (in 12 days)
```

## 5. Test suite

```
> python -m pytest -q

.............................................................            [100%]
61 passed in 2.00s
```

## 6. Interactive chat (model loads once per session)

```
> touchgrass chat --date 2026-03-15

Model loading for Denver, CO, zone 5b ...
Sprout - your offline garden coach (model runs on this machine)
Type /help for commands, /quit to leave. Ask anything about your garden.
you> when should I start my tomato seeds?
sprout> It's time to start your tomato seeds now, March 24.
you> /quit

[session: 1 question(s), qwen2.5-1.5b-instruct-q4_k_m.gguf, offline]
```

