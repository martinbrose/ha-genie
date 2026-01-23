"""Constants for the HA Genie integration."""

DOMAIN = "ha_genie"
CONF_GEMINI_API_KEY = "gemini_api_key"
CONF_HOUSE_BEDROOMS = "house_bedrooms"
CONF_HOUSE_SIZE = "house_size"
CONF_HOUSE_COUNTRY = "house_country"
CONF_HOUSE_RESIDENTS = "house_residents"
CONF_HOUSE_INFO = "house_info"
CONF_GEMINI_MODEL = "gemini_model"

# Entity Selectors
CONF_ENTITIES_TEMP = "entities_temp"
CONF_ENTITIES_HUMIDITY = "entities_humidity"
CONF_ENTITIES_RADON = "entities_radon"
CONF_ENTITIES_CO2 = "entities_co2"
CONF_ENTITIES_VOC = "entities_voc"
CONF_ENTITIES_CONTACT = "entities_contact"
CONF_ENTITIES_VALVES = "entities_valves"
CONF_ENTITIES_ENERGY = "entities_energy"
CONF_ENTITIES_GAS = "entities_gas"

DEFAULT_HOUSE_BEDROOMS = 3
DEFAULT_HOUSE_SIZE = 150
DEFAULT_HOUSE_RESIDENTS = 2
DEFAULT_HOUSE_COUNTRY = ""
DEFAULT_GEMINI_MODEL = "gemini-3-flash"

CONF_UPDATE_FREQUENCY = "update_frequency"
FREQUENCY_DAILY = "Daily"
FREQUENCY_WEEKLY = "Weekly"
DEFAULT_UPDATE_FREQUENCY = FREQUENCY_WEEKLY

CONF_DATA_AVERAGING = "data_averaging"
DATA_AVERAGING_HOURLY = "Hourly"
DATA_AVERAGING_DAILY = "Daily"
DATA_AVERAGING_WEEKLY = "Weekly"
DEFAULT_DATA_AVERAGING = DATA_AVERAGING_WEEKLY
