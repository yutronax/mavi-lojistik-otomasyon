from src.utils.vehicle_type_matcher import VehicleTypeMatcher

matcher = VehicleTypeMatcher()

test_cases = [
    "frigo kapalı aranıyor",
    "13 60 frigo kapalı ihtiyacı",
    "860 13 60 frigo kapalı",
    "860 özellikleri isteniyor frigo",
    "buğday soğan kapalı araç aranıyor",
    "meyve sebze yem frigo",
    "mısır portakal 1360"
]

print("=== VEHICLE TYPE MATCHER TEST RESULTS ===")
for msg in test_cases:
    print(f"\nMessage: '{msg}'")
    result = matcher.find_match(msg)
    print(f"Result : {result}")
