# St. Magnus Island Microgrid — Operator's Notes

## Demand Drivers

The island's hourly demand is driven by three things besides the time of
day and the day of the week: electric heating, the tourist ferry, and
public holidays.  All three show up in the metered history; these notes
explain the mechanisms so the numbers can be read correctly.

## 1. Electric Heating

Almost every home and business on the island heats electrically.  Once
the outdoor temperature drops below the point where the heating
controllers start calling for heat, demand rises with every further
degree of cold, in all hours of the day.

There is no thermostat cap or saturation in the controllers: the colder
it gets, the more heating load there is.  Past winters have brought
temperatures well below anything in a mild autumn, and the heating load
kept growing accordingly.  A forecast for a cold spell must not assume
the response levels off at the coldest temperature already observed.

## 2. Ferry

The tourist ferry calls on a published schedule.  Sailing days are
flagged in `data/calendar.csv` (`ferry_day = 1`) for the whole period,
including the weeks to forecast.  Day visitors raise demand during the
ferry's operating hours; outside those hours a ferry day looks like any
other day.

## 3. Public Holidays

Public holidays are flagged in `data/calendar.csv` (`holiday = 1`).
Businesses and schools close, so demand is lower than on a normal day of
the same weekday.  Islanders tend to leave for a long weekend when a
holiday falls next to one, so those holidays are quieter still.

## 4. Combined Effects

The drivers combine: a ferry sailing on a holiday adds its visitors on
top of the quieter holiday base, and heating load applies whatever the
calendar says.
