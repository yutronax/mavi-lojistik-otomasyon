# System Functions Guide - Database & Filtering Refactor

This guide explains the new and modified functions in the Mavi Lojistik Otomasyon system, focusing on filtering, deduplication, and location validation.

---

## 🚫 Blacklist Filtering

### `DataService.load_unprocessed_messages`
**What it does:** Loads messages that haven't been processed yet from the local storage.
**Why it was changed:** Added strict blacklist filtering during the loading phase.
**Logic:** It loads the blacklist from `data_blacklist.json` using `load_blacklist()`. As it iterates through each message, it extracts the sender's phone number, normalizes it, and checks if it exists in the blacklist. If found, the message is skipped (filtered out).
**Dependencies:** `load_blacklist`, `src.utils.phone_utils.normalize_phone`.
**Critical:** The phone number normalization must match the format in the blacklist file.

### `MongoDataService.load_unprocessed_messages`
**What it does:** Similar to its local counterpart, but fetches from MongoDB.
**Why it was changed:** Parallel logic was added to ensure consistency across storage backends.
**Logic:** Filters out messages from blacklisted numbers before returning the result set to the caller.

---

## 👯 Duplicate Detection

### `DataService.is_shipment_duplicate`
**What it does:** Checks if a shipment already exists in the system within a specific time window.
**Why it was changed:** The deduplication window was increased from 1 hour to **24 hours** to prevent "same day" duplicates.
**Logic:** It compares the "fingerprint" of the current shipment against existing shipments from the last 24 hours.
**Fingerprint Components:** Number, Route (Origin Il/Ilce -> Dest Il/Ilce), Vehicle Type, Cargo Type.

### `DataService._get_shipment_fingerprint`
**What it does:** Creates a unique string representation of a shipment's core data.
**Logic:** Combines `nereden_il`, `nereden_ilce`, `nereye_il`, `nereye_ilce`, `telefon`, `arac_tipi`, `kasa_tipi`, and `yuk_tipi`.
**Consistency:** Using sorted lists for types ensures that "Paletli, Komple" is the same as "Komple, Paletli".

---

## 🌍 Location Validation

### `LocationValidator` (New Utility)
**Location:** `src.utils.location_validator.py`
**What it does:** Uses `il_ilçe_mahalle.json` to verify if a location (Province/District) is a valid Turkish location.
**Why it's needed:** Identifies international or misspelled shipments that shouldn't be processed as domestic loads.
**Key Method:** `is_valid_city(city_name)` returns `True` if the city exists in the Turkey geography dataset.

### `OrchestratorSDK.process_message_task`
**What it does:** The main processing unit for incoming WhatsApp messages.
**Why it was changed:** Integrated the `LocationValidator` to flag shipments.
**Logic:** For each parsed shipment, it checks if `nereden_il` and `nereye_il` are valid Turkish cities. If either is invalid (e.g., a foreign country or unknown name), the shipment is marked with `invalid_location: True`.
**UI Integration:** Flagged shipments are still stored but can be visually distinguished or hidden in the GUI based on the `invalid_location` flag.

---

## 📝 Logging & Cleanup

### `OrchestratorSDK.check_periodic_cleanup`
**What it does:** Periodically (every 1 hour) cleans up old data and logs.
**Logic:** Triggers `data_service.cleanup_storage()` and `purge_old_logs(hours_back=1.0)`.
**User Rationale:** Prevents excessive disk usage by only keeping recent history relevant for operations.
