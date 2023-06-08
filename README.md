# Homeassistant MagentaTV Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

_Integration to integrate with media receivers for Telekom MagentaTV._

## Disclaimer

This project is at a very early stage.
Please reports bugs and request features to improve it over time.
Feel free to contribute!

## Currently Supported Devices

- Telekom Media Receiver 401
- Telekom Media Receiver 201

## Features

### Current

- Autodiscovery of media receivers within the local network
- See current (TV) playing status

### Planned

- Manual setup of a media receiver via host/ip and port
- Send Button Presses to the receiver (Remote Control via Homeassistant Service)
- Add MediaPlayer Controls like play/pause/mute etc
- Support more models
- Detect if App (Youtube/Prime/Netflix() is currently active on the receiver
- (Unknwon if possible) Start apps like Youtube/Netflix from Homeassistant

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=xyaren&repository=homeassistant-magentatv&category=integration)

or

1. Install [HACS](https://hacs.xyz/)
1. Add `https://github.com/Xyaren/homeassistant-magentatv` as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories)
1. Restart Home Assistant

### Manual

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `homeassistant-magentatv`.
1. Download _all_ the files from the `custom_components/homeassistant-magentatv/` directory (folder) in this repository.
1. Place the files you downloaded in the new directory (folder) you created.
1. Restart Home Assistant

## Adding a Receiver

1. Get your Telekom user id
    - Go to (web.magentatv.de/einstellungen/system)[https://web.magentatv.de/einstellungen/system]
    - Login
    - Copy your `ANID`
1. Configure a receiver
    - Detected by auto discovery at your (integrations dashboard)[https://my.home-assistant.io/redirect/integrations/]
    - Manually via (Add Integration)[https://my.home-assistant.io/redirect/config_flow_start/?domain=magentatv] )
1. Provide your user id from step 1.
1. Wait for the paring to finish (No confirmation on the tv neccecary)
1. Confirm adding the device and optionally assign it an area within homeassistant

<!---->

## Thanks

Thanks for (@humbertogontijo)[https://github.com/humbertogontijo] from (homeassistant-roborock)[https://github.com/humbertogontijo/homeassistant-roborock] for providing the inspiration to create an integration on my own.
Also serving as a reference repository on how to do things.

Also many thanks to (@ludeeus)[https://github.com/ludeeus] for (integration_blueprint)[https://github.com/ludeeus/integration_blueprint]

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
