# Changelog

## [1.2.2](https://github.com/watkins-matt/home-assistant-google-keep-sync/compare/1.2.1...1.2.2) (2026-11-21)


### Bug Fixes

* ask for a new token when Google rejects it ([#123](https://github.com/watkins-matt/home-assistant-google-keep-sync/issues/123)) ([426122e](https://github.com/watkins-matt/home-assistant-google-keep-sync/commit/426122e750f347c874abc5e29f090b55486f56d1))
* **config_flow:** check the submitted token during setup and reauth ([#122](https://github.com/watkins-matt/home-assistant-google-keep-sync/issues/122)) ([ae3902b](https://github.com/watkins-matt/home-assistant-google-keep-sync/commit/ae3902bc0eda6e4cb01311f84e33c687c94bb641))
* **config_flow:** show how to get the token in the setup and reauth forms ([#125](https://github.com/watkins-matt/home-assistant-google-keep-sync/issues/125)) ([b149f01](https://github.com/watkins-matt/home-assistant-google-keep-sync/commit/b149f019d49135a935132c0ff09ee7a13364e3c1))
* delete saved Google Keep state when an entry is removed ([#121](https://github.com/watkins-matt/home-assistant-google-keep-sync/issues/121)) ([0e286b4](https://github.com/watkins-matt/home-assistant-google-keep-sync/commit/0e286b4b2c229e62ece012a9ec529413264e35d2))

## [1.2.1](https://github.com/watkins-matt/home-assistant-google-keep-sync/compare/1.2.0...1.2.1) (2026-11-14)


### Bug Fixes

* **api:** accept master tokens of 200+ characters ([#111](https://github.com/watkins-matt/home-assistant-google-keep-sync/issues/111)) ([aad94e9](https://github.com/watkins-matt/home-assistant-google-keep-sync/commit/aad94e92158444f9cba76ceaa538ed7872771bbd))
* **api:** save Keep state after sync ([#108](https://github.com/watkins-matt/home-assistant-google-keep-sync/issues/108)) ([34efd3d](https://github.com/watkins-matt/home-assistant-google-keep-sync/commit/34efd3d101e141f1f2c5e88450e1c05383b2f5b0))
* **config_flow:** show invalid_token_format error on reauth ([#118](https://github.com/watkins-matt/home-assistant-google-keep-sync/issues/118)) ([3996082](https://github.com/watkins-matt/home-assistant-google-keep-sync/commit/399608206c40870f9ce7440db74ff5f4d4f1fba9))

## [1.2.0](https://github.com/watkins-matt/home-assistant-google-keep-sync/compare/1.1.0...1.2.0) (2026-11-09)


### Features

* dev container with Home Assistant core from source ([#97](https://github.com/watkins-matt/home-assistant-google-keep-sync/issues/97)) ([551c1f1](https://github.com/watkins-matt/home-assistant-google-keep-sync/commit/551c1f1758f81abf5edc20d0da3c0b8463327653))


### Bug Fixes

* avoid direct config entry mutation during reauth ([#95](https://github.com/watkins-matt/home-assistant-google-keep-sync/issues/95)) ([3299816](https://github.com/watkins-matt/home-assistant-google-keep-sync/commit/329981615049f2f13ae2a04668fd111097ab6edf))
* **deps:** allow gpsoauth 2.0.0 and later ([#96](https://github.com/watkins-matt/home-assistant-google-keep-sync/issues/96)) ([b6d4d0f](https://github.com/watkins-matt/home-assistant-google-keep-sync/commit/b6d4d0f21600d5ed9f9857747cc6b8ea2eae21c4))
* run and debug targets in .vscode/launch.json ([#98](https://github.com/watkins-matt/home-assistant-google-keep-sync/issues/98)) ([9a1b256](https://github.com/watkins-matt/home-assistant-google-keep-sync/commit/9a1b256661c35964ddf5a89b80551d6cf9741714))
