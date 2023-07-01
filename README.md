<img alt="logo" align="right" width="300" height="150" src="https://upload.wikimedia.org/wikipedia/commons/1/13/Magenta_TV_Logo_%282021%29.svg">

# Homeassistant MagentaTV Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
![Dynamic JSON Badge](coverage-shield)
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
- Manual setup of a media receiver via host/ip and port
- Send button Presses to the receiver (remote control via Homeassistant service)
  Check out the service `magentatv.send_key`
- Configurable listen/advertised address and port used for receiving events (for runing in Docker or NAT situations)
- MediaPlayer controls like play/pause/mute/volume/on/off

### Planned
- Support more device models
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


## Docker considerations
In order to receive events from the mediareceivers, the integration needs to create a server listening on port 11223.
Make sure this port is reachable from the receivers. In case of homeassistant running in docker ( except running in `host` mode), this requires mapping port 11223 to the outside.

Check out the Configuration section below for configuration related to setting a the correct advertisement address and port in docker scenarios

## Adding a Receiver

1. Get your Telekom user id
   This id is required for paring the integration with your receiver. It therefore has to belong to the same account, the receiver is running on.
    - Go to [web.magentatv.de/einstellungen/system](https://web.magentatv.de/einstellungen/system)
    - Login
    - Copy your `ANID` from the system info [Screeenshot](https://i.imgur.com/wY0u7JL.png)
1. Configure a receiver
    - Detected by auto discovery at your [integrations dashboard](https://my.home-assistant.io/redirect/integrations/)
    - Manually via [Add Integration](https://my.home-assistant.io/redirect/config_flow_start/?domain=magentatv)
1. Provide your user id from step 1.
1. Wait for the paring to finish (No confirmation on the tv neccecary)
1. Confirm adding the device and optionally assign it an area within homeassistant

## Configuration
You can control the used port and address used by the integration to receive events from the receivers using the yaml config.
In most cases these are not required.
```yaml
magentatv:
magentatv:
  ## Address to listen for UPNP subscription callbacks, must be reachable from the media receivers.
  ## Default 0.0.0.0
  # listen_address: "0.0.0.0"

  ## Port for UPNP subscription callbacks, must be reachable from the media receivers.
  ## For Homeassistant running in docker, this needs to be mapped.
  ## Default: 11223
  # listen_port:


  ## Address to advertise to receiver for callback. This is auto detected by default and only needs to be overwritten in case of nat/docker setups.
  ## This can NOT be a dns name
  # advertise_address:

  ## Port to advertise to receiver for callback. This equals the listen_port by default and only needs to be overwritten in case of port mapping
  # advertise_port:


  ## Telekom user id used as default for configuration flows. Optional.
  ## Default None
  # user_id: 120049010000000017944901
```


## Thanks

Thanks for [@humbertogontijo](https://github.com/humbertogontijo) from [homeassistant-roborock](https://github.com/humbertogontijo/homeassistant-roborock) for providing the inspiration to create an integration on my own.
Also serving as a reference repository on how to do things.

Also many thanks to [@ludeeus](https://github.com/ludeeus) for [integration_blueprint](https://github.com/ludeeus/integration_blueprint)

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
[coverage-shield]: https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fxyaren.github.io%2Fhomeassistant-magentatv%2Fcoverage%2Fcoverage.json&query=%24.totals.percent_covered_display&suffix=%25&style=for-the-badge&label=Coverage&color=green