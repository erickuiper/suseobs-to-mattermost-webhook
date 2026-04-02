"""Internal normalized alert for templating."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedAlert:
    """Fields available to MESSAGE_TEMPLATE placeholders."""

    summary: str
    severity: str
    status: str
    error_details: str
    resource_name: str
    resource_type: str
    resource_identifier: str
    suse_obs_name: str
    suse_obs_url: str
    notification_id: str
    monitor_name: str
    monitor_link: str
    component_link: str
    is_close_event: bool = False
    monitoring_source_key: str = ""
    monitor_identifier: str = ""

    def as_template_dict(self) -> dict[str, str]:
        return {
            "summary": self.summary,
            "severity": self.severity,
            "status": self.status,
            "error_details": self.error_details,
            "resource_name": self.resource_name,
            "resource_type": self.resource_type,
            "resource_identifier": self.resource_identifier,
            "suse_obs_name": self.suse_obs_name,
            "suse_obs_url": self.suse_obs_url,
            "notification_id": self.notification_id,
            "monitor_name": self.monitor_name,
            "monitor_link": self.monitor_link,
            "component_link": self.component_link,
            "monitor_identifier": self.monitor_identifier,
            "monitoring_source_key": self.monitoring_source_key,
        }
