# Homeassistant MagentaTV Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

_Integration to integrate with media receivers for Telekom MagentaTV._

## Currently Supported Devices

- Telekom Media Receiver 401
- Telekom Media Receiver 201

## Features

### Current

- See current (TV) playing status

### Planned

- Send Button Presses to the receiver (Remote Control)

## Installation

### HACS (Recommended)

1. Install [HACS](https://hacs.xyz/)
1. Add `https://github.com/Xyaren/homeassistant-magentatv` as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories)
1. Restart Home Assistant
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "MagentaTV"

### Manual

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `homeassistant-magentatv`.
1. Download _all_ the files from the `custom_components/homeassistant-magentatv/` directory (folder) in this repository.
1. Place the files you downloaded in the new directory (folder) you created.
1. Restart Home Assistant
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "MagentaTV"

## Configuration is done in the UI

1. Optain your Telekom user id
    - TODO
1. Configure a receiver
    - Detected by auto discovery at your (integrations dashboard)[https://my.home-assistant.io/redirect/integrations/]
    - Manually via (Add Integration)[https://my.home-assistant.io/redirect/config_flow_start/?domain=magentatv] )
1. Provide your user id from step 1.
1. Wait for the paring to finish (No confirmation on the tv neccecary)
1. Confirm adding the device and optionally assign it an area within homeassistant

<!---->

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

***

[homeassistant-magentatv]: https://github.com/xyaren/homeassistant-magentatv
[buymecoffee]: https://www.buymeacoffee.com/xyaren
[buymecoffeebadge]: https://img.shields.io/badge/🍕%20buy%20me%20a%20slice%20of%20pizza-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/xyaren/homeassistant-magentatv.svg?style=for-the-badge
[commits]: https://github.com/xyaren/homeassistant-magentatv/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/xyaren/homeassistant-magentatv.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40xyaren-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/xyaren/homeassistant-magentatv.svg?style=for-the-badge
[releases]: https://github.com/xyaren/homeassistant-magentatv/releases
