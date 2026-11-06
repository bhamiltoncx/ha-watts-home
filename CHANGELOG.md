# Changelog

## [1.2.2](https://github.com/bhamiltoncx/ha-watts-home/compare/v1.2.1...v1.2.2) (2026-11-06)


### Bug Fixes

* map Heat/Cool Today sensors to their own energy channels ([#43](https://github.com/bhamiltoncx/ha-watts-home/issues/43)) ([329056b](https://github.com/bhamiltoncx/ha-watts-home/commit/329056b03640453d8163a48faeeb47abd4c8fc04))
* read today's run time from the device's weekday slot ([#47](https://github.com/bhamiltoncx/ha-watts-home/issues/47)) ([fb9aa0e](https://github.com/bhamiltoncx/ha-watts-home/commit/fb9aa0e845002c2c074add41a87a910d571dac9d))
* report Heat/Cool Today as run time hours, not kWh ([#44](https://github.com/bhamiltoncx/ha-watts-home/issues/44)) ([e43cf44](https://github.com/bhamiltoncx/ha-watts-home/commit/e43cf44c8c6d89dcfba68d5ee2482734c6a7aec6))

## [1.2.1](https://github.com/bhamiltoncx/ha-watts-home/compare/v1.2.0...v1.2.1) (2026-11-05)


### Bug Fixes

* provide the native climate temperature properties ([#38](https://github.com/bhamiltoncx/ha-watts-home/issues/38)) ([f04a10d](https://github.com/bhamiltoncx/ha-watts-home/commit/f04a10d05b012ff3fbb7a54d8864bb43c8c777ab))

## [1.2.0](https://github.com/bhamiltoncx/ha-watts-home/compare/v1.1.3...v1.2.0) (2026-10-20)


### Features

* add config entry diagnostics ([#33](https://github.com/bhamiltoncx/ha-watts-home/issues/33)) ([840ffb6](https://github.com/bhamiltoncx/ha-watts-home/commit/840ffb62c51732bea82adb42da67de367d730997))


### Bug Fixes

* convert setpoint steps with TemperatureDeltaConverter ([#35](https://github.com/bhamiltoncx/ha-watts-home/issues/35)) ([01c47ed](https://github.com/bhamiltoncx/ha-watts-home/commit/01c47ed58ededf9e323f140829d0494e49bc8b62))

## [1.1.3](https://github.com/bhamiltoncx/ha-watts-home/compare/v1.1.2...v1.1.3) (2026-10-08)


### Bug Fixes

* express the setpoint step in the unit HA displays ([#28](https://github.com/bhamiltoncx/ha-watts-home/issues/28)) ([6aeb9a0](https://github.com/bhamiltoncx/ha-watts-home/commit/6aeb9a06928c54d3ea11eb56cf656c526a1fdab7))
* keep sub-degree readings on a Fahrenheit system ([#27](https://github.com/bhamiltoncx/ha-watts-home/issues/27)) ([be01d61](https://github.com/bhamiltoncx/ha-watts-home/commit/be01d612040dc4c622007250fcceb6b9e0993663))

## [1.1.2](https://github.com/bhamiltoncx/ha-watts-home/compare/v1.1.1...v1.1.2) (2026-09-15)


### Bug Fixes

* poll devices from every Watts Home location ([#25](https://github.com/bhamiltoncx/ha-watts-home/issues/25)) ([dd36a37](https://github.com/bhamiltoncx/ha-watts-home/commit/dd36a37f0cd49b3df41027a99fd0ac4d6ffbea9c))

## [1.1.1](https://github.com/bhamiltoncx/ha-watts-home/compare/v1.1.0...v1.1.1) (2026-08-23)


### Bug Fixes

* keep the floor entity's upper setpoint bound usable ([#17](https://github.com/bhamiltoncx/ha-watts-home/issues/17)) ([412f70d](https://github.com/bhamiltoncx/ha-watts-home/commit/412f70dca25d6bd477ef22c9619cb8650c7f4060))
* support Tekmar devices which are missing low/high setpoint ([#15](https://github.com/bhamiltoncx/ha-watts-home/issues/15)) ([cfae065](https://github.com/bhamiltoncx/ha-watts-home/commit/cfae0658dd65d5f9df3e0c48fc8548a4bc3e39ea))
* support the Tekmar 170 Wi-Fi Setpoint Control ([#21](https://github.com/bhamiltoncx/ha-watts-home/issues/21)) ([c67c39c](https://github.com/bhamiltoncx/ha-watts-home/commit/c67c39c1c38cfce657598a9d17d73107c623c107))

## [1.1.0](https://github.com/bhamiltoncx/ha-watts-home/compare/v1.0.1...v1.1.0) (2026-08-07)


### Features

* add reauthentication flow to the config flow ([#9](https://github.com/bhamiltoncx/ha-watts-home/issues/9)) ([cd1cbac](https://github.com/bhamiltoncx/ha-watts-home/commit/cd1cbac2afb2a1c987b533c7ed18e4909186dfde))


### Bug Fixes

* retry transient 5xx from the auth server ([#7](https://github.com/bhamiltoncx/ha-watts-home/issues/7)) ([087c73a](https://github.com/bhamiltoncx/ha-watts-home/commit/087c73a6538114a77b3a954ebc178620d61c2fb5))
