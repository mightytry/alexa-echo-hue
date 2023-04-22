# Alexa-Echo-Hue
Amazon alexa echo hue lamp emulation for python

Thanks to [falk0069](https://github.com/falk0069/hue-upnp) and [IcynatorHD](https://www.npmjs.com/package/node-red-contrib-local-alexa-devices) for their work!


## Table of Contents
- [Alexa-Echo-Hue](#alexa-echo-hue)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Installation](#installation)
  - [Usage](#usage)
    - [Hub](#hub)
      - [Arguments](#arguments)
      - [Methods](#methods)
      - [Example](#example)
    - [Device](#device)
      - [Arguments](#arguments-1)
      - [Overrides](#overrides)
      - [Example](#example-1)
    - [Example](#example-2)
    - [Contributing](#contributing)
      - [Requirements (for development)](#requirements-for-development)
  

## Features
- Emulate a Philips Hue Light Bulb
- Control your devices with Alexa Echo
- Asyncronous processing

## Installation
- Install Python 3.11 or higher
- And: ```pip install echohue```


## Usage
Create a hub object and add devices to it. Then run the hub.

### Hub
#### Arguments
| Argument | Type | Description | Default |
| --- | --- | --- | --- |
| debug | bool | Enable debug mode | False |

#### Methods
| Method | Args | Description |
| --- | --- | --- |
| add | Device | Add a device to the hub |
| run | - | Run the hub |

#### Example
```python
async with Hub() as hub:
    hub.add(Device('Test Device', True, 254))
    await hub.run()
```

### Device
Has to return **True** or **None** if the override was successful, otherwise **False**.

**Note: if the override returns false, the device value will not be updated. And Echo will receive an error. The same applies to if the task takes too long.**
#### Arguments
| Argument | Type | Description | Default |
| --- | --- | --- | --- |
| name | str | The name of the device | - |
| on | bool | The state of the device | False |
| brightness | int (1-254) | The brightness of the device | 1 |

#### Overrides
| Override | Args | Description |
| --- | --- | --- |
on_on | - | Called when the device is turned on |
on_off | - | Called when the device is turned off |
on_bri | int (1-254) | Called when the brightness is changed |
on_ct | int (153-500) | Called when the color temperature is changed |
on_xy | tuple (float, float) | Called when the color is changed |
on_hue | int (0-65535) | Called when the hue is changed |
on_sat | int (0-254) | Called when the saturation is changed |

#### Example
```python
from echohue import Hub, Device
class Lamp(Device):
    def __init__(self, name, on, brightness):
        super().__init__(name, on, brightness)

    async def on_on(self):
        print('Lamp turned on')
    async def on_off(self):
        print('Lamp turned off')
    async def on_bri(self, bri):
        print(f'Lamp brightness changed to {bri}')
```

### Example
This example will create a hub with a device called "Lamp" and print the state changes to the console.
```python
import asyncio
from echohue import Hub, Device

class Lamp(Device):
    def __init__(self, name, on=True, brightness=1):
        super().__init__(name, on, brightness)

    async def on_on(self):
        print('Lamp turned on')
    async def on_off(self):
        print('Lamp turned off')
    async def on_bri(self, bri):
        print(f'Lamp brightness changed to {bri}')

async def main():
    async with Hub() as hub:
        hub.add(Lamp('Test Device'))
        await hub.run()

if __name__ == '__main__':
    asyncio.run(main())
```

## Contributing
Pull requests are welcome and **greatly appreciated**!. For major changes, please open an issue first to discuss what you would like to change.
### Requirements (for development)
- Python 3.11 or higher
- [Packages](https://raw.githubusercontent.com/mightytry/alexa-echo-hue/main/requirements.txt)