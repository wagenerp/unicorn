# UNified Interface Co-ordination Notation specification and reference code library
## Summary

Unicorn is a combination of conventions and an interface description language used to coordinate devices and services through a common publish-subscribe middleware.

Originally developed while making DIY smart home devices and organizing them to communicate via MQTT, these are the key concepts:
* Any number of uniquely named *devices* announce themselves, describe publish-subscribe topics they operate with and announce their departure (e.g. via last will messages).
  * Announcements (both connection and disconnection) are sent to topic `/unicorn`.
* Topics described by devices fulfill one of three roles:
  * *Command*: Devices listen to these topics and react to messages posted, consisting of plaintext shell like commands, described via the *completion* IDL.
  * *Measurement*: Devices report one or more quantities as a sequence of plaintext numbers. Units and names of these quantities are described via the *measruement* IDL.
  * *Event*: Messages delivered by the device describe a distinct event in time, such as button presses. Described via the *event* IDL.
* Device topics *always* start with the device's unique name followed by a suitable delimiter (forward slash in case of MQTT).
  * the IDL to any given topic `<device/topic>` is a JSON string delivered as a retained message to topic `/unicorn/device/topic`. 
* A single special service may be present on the publish-subscribe network, called the *unicorn services manager*, responsible for
  * Maintaining a list of devices seen (currently active or not), storing the last seen connect message under `/unicorn/register/<device>`.
  * Maintaining a list of currently active devices similar to the register under `/unicorn/active/<device>`.
  * Removing any retained IDL messages when a device disconnects - effectively augmenting the last will message to perform more cleanup.


Included in this repository are
  * The unicorn interface description language as json schema and as helper code for various languages.
  * A python-based autocompletion implementation for the command IDL and an interactive interpreter.