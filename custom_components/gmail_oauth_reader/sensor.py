from dataclasses import asdict
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATE_IDLE
from .coordinator import GmailDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GmailDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GmailLatestEmailSensor(coordinator, entry)])


class GmailLatestEmailSensor(
    CoordinatorEntity[GmailDataUpdateCoordinator], SensorEntity
):
    _attr_has_entity_name = True
    _attr_translation_key = "latest_email"

    def __init__(
        self,
        coordinator: GmailDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_latest_email"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.unique_id))},
            name=f"Gmail ({entry.title})",
            manufacturer="Google",
            model="Gmail API",
        )

    @property
    def native_value(self) -> str:
        if self.coordinator.data is not None:
            return self.coordinator.data.message_id
        return STATE_IDLE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        message = self.coordinator.data or self.coordinator.last_message
        attributes = asdict(message) if message is not None else {}
        attributes["unread_count"] = self.coordinator.unread_count
        attributes["queue_size"] = self.coordinator.queue_size
        attributes["messages"] = [
            asdict(email_item)
            for email_item in reversed(self.coordinator.recent_emails)
        ]
        return attributes
