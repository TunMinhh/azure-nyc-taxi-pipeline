# NYC Taxi Trip Data — Data Dictionary

This document summarizes the fields shown in the official data dictionaries for **Yellow Taxi** and **Green Taxi** trip records.

## 1. Yellow Taxi

| Field | Description / Values |
|---|---|
| `VendorID` | Code identifying the TPEP provider that provided the record: `1` = Creative Mobile Technologies, LLC; `2` = Curb Mobility, LLC; `6` = Myle Technologies Inc; `7` = Helix. |
| `tpep_pickup_datetime` | Date and time when the meter was engaged. |
| `tpep_dropoff_datetime` | Date and time when the meter was disengaged. |
| `passenger_count` | Number of passengers in the vehicle. |
| `trip_distance` | Elapsed trip distance in miles reported by the taximeter. |
| `RatecodeID` | Final rate code in effect at the end of the trip: `1` = Standard rate; `2` = JFK; `3` = Newark; `4` = Nassau or Westchester; `5` = Negotiated fare; `6` = Group ride; `99` = Null/unknown. |
| `store_and_fwd_flag` | Whether the trip record was held in vehicle memory before being sent to the vendor because the vehicle lacked a server connection. `Y` = store and forward trip; `N` = not a store and forward trip. |
| `PULocationID` | TLC Taxi Zone in which the taximeter was engaged (pickup location). |
| `DOLocationID` | TLC Taxi Zone in which the taximeter was disengaged (drop-off location). |
| `payment_type` | Numeric code for how the passenger paid: `0` = Flex Fare trip; `1` = Credit card; `2` = Cash; `3` = No charge; `4` = Dispute; `5` = Unknown; `6` = Voided trip. |
| `fare_amount` | Time-and-distance fare calculated by the meter. |
| `extra` | Miscellaneous extras and surcharges. |
| `mta_tax` | Tax automatically triggered based on the metered rate in use. |
| `tip_amount` | Tip amount. This field is automatically populated for credit-card tips; cash tips are not included. |
| `tolls_amount` | Total amount of all tolls paid in the trip. |
| `improvement_surcharge` | Improvement surcharge assessed per trip at the flag drop; the surcharge began being levied in 2015. |
| `total_amount` | Total amount charged to passengers; does not include cash tips. |
| `congestion_surcharge` | Total amount collected in trip for the NYC congestion surcharge. |
| `airport_fee` | Fee for pickup only at LaGuardia and John F. Kennedy airports. |
| `cbd_congestion_fee` | Per-trip charge for the MTA's Congestion Relief Zone, starting January 5, 2025. |

## 2. Green Taxi

| Field | Description / Values |
|---|---|
| `VendorID` | Code identifying the LPEP provider that provided the record: `1` = Creative Mobile Technologies, LLC; `2` = Curb Mobility, LLC; `6` = Myle Technologies Inc; `7` = Helix. |
| `lpep_pickup_datetime` | Date and time when the meter was engaged. |
| `lpep_dropoff_datetime` | Date and time when the meter was disengaged. |
| `store_and_fwd_flag` | Whether the trip record was held in vehicle memory before being sent to the vendor because the vehicle lacked a server connection. `Y` = store and forward trip; `N` = not a store and forward trip. |
| `RatecodeID` | Final rate code in effect at the end of the trip: `1` = Standard rate; `2` = JFK; `3` = Newark; `4` = Nassau or Westchester; `5` = Negotiated fare; `6` = Group ride; `99` = Null/unknown. |
| `PULocationID` | TLC Taxi Zone in which the taximeter was engaged (pickup location). |
| `DOLocationID` | TLC Taxi Zone in which the taximeter was disengaged (drop-off location). |
| `passenger_count` | Number of passengers in the vehicle. |
| `trip_distance` | Elapsed trip distance in miles reported by the taximeter. |
| `fare_amount` | Time-and-distance fare calculated by the meter. |
| `extra` | Miscellaneous extras and surcharges. |
| `mta_tax` | Tax automatically triggered based on the metered rate in use. |
| `tip_amount` | Tip amount. This field is automatically populated for credit-card tips; cash tips are not included. |
| `tolls_amount` | Total amount of all tolls paid in the trip. |
| `improvement_surcharge` | Improvement surcharge assessed per trip at the flag drop; the surcharge began being levied in 2015. |
| `total_amount` | Total amount charged to passengers; does not include cash tips. |
| `payment_type` | Numeric code for how the passenger paid: `0` = Flex Fare trip; `1` = Credit card; `2` = Cash; `3` = No charge; `4` = Dispute; `5` = Unknown; `6` = Voided trip. |
| `trip_type` | Code indicating whether the trip was a street-hail or a dispatch trip, assigned automatically based on the metered rate but editable by the driver: `1` = Street-hail; `2` = Dispatch. |
| `congestion_surcharge` | Total amount collected in trip for the NYC congestion surcharge. |
| `cbd_congestion_fee` | Per-trip charge for the MTA's Congestion Relief Zone, starting January 5, 2025. |
