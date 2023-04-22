# Path: src\echohue\defaults.py
ALL = {
  "state": {
    "on": None,
    "bri": None,
    "hue": None,
    "sat": None,
    "effect": "none",
    "xy": None,
    "ct": None,
    "alert": "none",
    "colormode": "hs",
    "mode": "homeautomation",
    "reachable": True
  },
  "swupdate": {
    "state": "noupdates",
    "lastinstall": ""
  },
  "type": "Extended color light",
  "name": None,
  "modelid": "LCT007",
  "manufacturername": "Philips",
  "productname": "Hue color lamp",
  "capabilities": {
    "certified": True,
    "control": {
      "mindimlevel": 5000,
      "maxlumen": 600,
      "colorgamuttype": "A",
      "colorgamut": [
        [0.675, 0.322],
        [0.409, 0.518],
        [0.167, 0.04]
      ],
      "ct": {
        "min": 153,
        "max": 500
      }
    },
    "streaming": {
      "renderer": True,
      "proxy": False
    }
  },
  "config": {
    "archetype": "sultanbulb",
    "function": "mixed",
    "direction": "omnidirectional"
  },
  "uniqueid": "00:11:22:33:44:55:66:77-88",
  "swversion": "5.105.0.21169"
}

GETSTATE = {
    "state": {
        "on": None,
        "bri": None,
        "hue": None,
        "sat": None,
        "effect": "none",
        "xy": None,
        "ct": None,
        "alert": "none",
        "colormode": None,
        "mode": "homeautomation",
        "reachable": True
    },
    "swupdate": {
        "state": "noupdates",
        "lastinstall": None
    },
    "type": "Extended color light",
    "name": None,
    "modelid": "LCT007",
    "swversion": "5.105.0.21169"
  }