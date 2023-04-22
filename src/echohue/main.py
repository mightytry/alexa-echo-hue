import asyncio
from contextlib import AbstractAsyncContextManager
import copy
import datetime
import socket
import struct
import email.utils
import uuid
import re
import sys
import logging
import logging.handlers
import json
from .defaults import ALL, GETSTATE

M_SEARCH_REQ_MATCH = "M-SEARCH"

UPNP_BROADCAST = """NOTIFY * HTTP/1.1
HOST: 239.255.255.250:1900
CACHE-CONTROL: max-age=100
LOCATION: http://{}:{}/description.xml
SERVER: FreeRTOS/6.0.5, UPnP/1.0, IpBridge/0.1
NTS: ssdp:alive
NT: upnp:rootdevice
USN: uuid:2f402f80-da50-11e1-9b23-{}::upnp:rootdevice

""".replace("\n", "\r\n")


# IP, PORT, ST
UPNP_RESPOND_TEMPLATE = """HTTP/1.1 200 OK
CACHE-CONTROL: max-age=100
EXT:
LOCATION: http://{}:{}/description.xml
SERVER: FreeRTOS/6.0.5, UPnP/1.0, IpBridge/0.1
ST: {}
USN: uuid:2f402f80-da50-11e1-9b23-{}::upnp:rootdevice

""".replace("\n", "\r\n")

# TODO: jimboca: check others to see if they are specifying this?
# CACHE-CONTROL: max-age=86400
# EXT:
# LOCATION: http://{}:{}/description.xml
# SERVER: FreeRTOS/6.0.5, UPnP/1.0, IpBridge/0.1
# ST: urn:schemas-upnp-org:device:basic:1
# USN: uuid:Socket-1_0-221438K0100073::urn:schemas-upnp-org:device:basic:1

# updated modelName and removed extra tabs and \r to match examples on web
DESCRIPTION_XML = """HTTP/1.1 200 OK
Content-type: text/xml
Connection: Keep-Alive

<?xml version="1.0" encoding="UTF-8" ?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
<specVersion>
<major>1</major>
<minor>0</minor>
</specVersion>
<URLBase>http://{}:{}/</URLBase>
<device>
<deviceType>urn:schemas-upnp-org:device:Basic:1</deviceType>
<friendlyName>Philips hue ({})</friendlyName>
<manufacturer>Royal Philips Electronics</manufacturer>
<manufacturerURL>http://www.philips.com</manufacturerURL>
<modelDescription>Philips hue Personal Wireless Lighting</modelDescription>
<modelName>Philips hue bridge 2012</modelName>
<modelNumber>929000226503</modelNumber>
<modelURL>http://www.meethue.com</modelURL>
<serialNumber>{}</serialNumber>
<UDN>uuid:2f402f80-da50-11e1-9b23-{}</UDN>
<serviceList>
<service>
<serviceType>(null)</serviceType>
<serviceId>(null)</serviceId>
<controlURL>(null)</controlURL>
<eventSubURL>(null)</eventSubURL>
<SCPDURL>(null)</SCPDURL>
</service>
</serviceList>
<presentationURL>index.html</presentationURL>
<iconList>
<icon>
<mimetype>image/png</mimetype>
<height>48</height>
<width>48</width>
<depth>24</depth>
<url>hue_logo_0.png</url>
</icon>
<icon>
<mimetype>image/png</mimetype>
<height>120</height>
<width>120</width>
<depth>24</depth>
<url>hue_logo_3.png</url>
</icon>
</iconList>
</device>
</root>
""".replace("\n", "\n")  # was \r\n

# 20150920-Added in case it is used for discovery
APICONFIG_JSON = """
[{"swversion":"01008227","apiversion":"1.2.1","name":"Smartbridge 1","mac":"%s",}]
"""

NEWDEVELOPERSYNC_JSON = """
[{"success":{"%s":"c6260f982b43a226b5542b967f612ce"}}]
""" % ("username")

# example template values: "success", "1", "on", "true"
PUTRESP_TEMPLATE_JSON = """
[{"%s":{"/lights/%s/state/%s":%s}}]
"""

JSON_HEADERS = """HTTP/1.1 200 OK
CONTENT-LENGTH: %d
CONTENT-TYPE: application/json charset="utf-8"
DATE: %s
EXT:
SERVER: Unspecified, UPnP/1.0, Unspecified
CONNECTION: close

%s"""


ICON_HEADERS = """HTTP/1.1 200 OK
Content-type: image/png

""".replace("\n", "\r\n")

ICON_SMALL = b"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"
ICON_BIG = b"iVBORw0KGgoAAAANSUhEUgAAAHgAAAB4CAYAAAA5ZDbSAAAAB3RJTUUH3AgNBw4nVfRriAAAAAlwSFlzAAAewgAAHsIBbtB1PgAAAARnQU1BAACxjwv8YQUAACA+SURBVHja7V0LeFXVlV7ncZ/JTULCKwGCgYCAgiAPFakKVfA5tqjVftNqq1OnOuNX/apfR7+pM/aztR2tdpy2VltHnaqttp3p2LG1zqhVUVBBCwooLwNEMEAgCUlucl9n1trn7JN9z93nce9NVOhdfJtzzr5nr3PO/vd67LX2OVGgdNIXL168UNf1ZaqqzsfjViwTFEVJ4DYknoh1ZVzm6CXDMJzHWdz0YenAsh2PN6TT6Rd7e3tf3LBhQ18p1yi655csWTIdAftqLpf7PB6OA4bfEBsnmBVw3ckJsLOO7+O2FzdPoSA9sGrVqheLuUbg3l+wYMGUSCRyOwJ2CV5IZ40t8LxArADsTTKQxd8EkNkGBevVVCp1yxtvvPFSEP5Bel9Dqb0RGd+K+3ECzE1iZWBWAPYmiZqWHotbLDns15/39fVdv379+i4v/p69P3fu3DGxWOwJZHYG18MiwBUJLp/8JNi5FaQaN0YbSvPF69ate9ONh2vvn3TSSdNQFf8Bd6dyUGWAViS4PPKywzJpdqptss/Yx5etXr36aRl/VVY5b9488ohfAAtckYoBrALuyJCjX6vRfP4GfaQLpOc6KxYuXNgQCoVW4+40zkyUXDfAK9JbOnnZYRevWuaA9eN26Zo1a14XeTkRUBYtWvQHBGa5YpJZWVHPI0pBAebHEjXN9lGSd+NmHnrYnfx8XWx8yimnXMfBpWMnwF7qugJw6VSKHRb3+TH6TBNxcx+Wz/HzbQTQ7jZpmrYZT6pxU8sV9TwyFDTgIe6L4DrqiM5Hz/r3VGdLcDwe/yZuamRToIp6HnmSSSrvQ5k6doIr1ClY7sDDZ7DkGIf58+c3IrMdWKJuwFbU88jScNlhLsVojz/z1ltvPcUkOBqNXkXg0r4TOLegRiW4MbxUSsBDVmcdKwjwtbh9iiGBc6iNCMqsivR+fFSuHXbWI8AZnO5O1E8++eRWdK5m0g8y4IoNTQb5vUJyCirFsn3x2Co6lnN1RPp0LNI4s5/3LPvNra5C/jTMdph2T9dReue7ec7FAsw9vwrApVEQgHkfo1AW1DtBxnPm6dlsttVNDZciwRVwS6fhlmAsU0mCx1NlqQCDCLbs9woFphFQ0VVkiBOl3sy33t4O1VlTVTw+eTysq6+pgFsGjQDAQACrBIoYOQlyI6jaYexgGmosgMOpdFE8KjTyRHjofp6zm9OUyWQAx0n+ccXJKpmKFbCg59I0ydf+ugEs4MskmniJ/CoUnIY70MELOVme4Ug3R0vFdiLR78RLs+orIBdHw5UydNbrJIle8WcZwMwGkwQLlMO6jFBXAbg4GgkHiwGM5JkSlIFNDdPpdN5FVVUhZhAKhfLaV8ifylHPbvu2F51KpQrsrJ8UU+OUA+AcetMEungzFYCDUSnSK+57xKNBJ4kTQ5NekizWZRwqWtVUCIfDTIpFqoDsTV4JBvH3YkAV63WuaoM6WnzOTJIvEkkw1fEYqUgVkOVUjGoWj4N4z7YEcxtM5CbFMoBFW0tEEkx1TgkW21con0qVXq/fpF40UdBgB986VbRogyspRG9yA7ZY2yue57YIT3fOW72kWARJc8yDVVVl0ssl2A3Qv3SgSwWXbwMs18lX0SR1BE6xEpzN5ttasr0Uzaqs2XKnICs2ZOcVK72uEhzUFjv3+TENFCrOehn9pYHsZro4GOIU1BlU4r8798U6sZ4XOta51DlBFRMHIjP7dygcZW6xaDpTxd81xYAMIB8siuPBSiEV+Wmq9doGbrI5tWReQ72EPDUuAeRblMeTAcAlCoWJ9hTqc/Phi1LNQfadUyVdekPgP2L8PMBafIiFqR44PtcLLVoS6kMpnHSjGkfnuwvt9G41Bu/kEvDq4CjoyoWK/pYEXf+ixbvgiuVt7IsgW/dVw/U/OLFszTBrdid87subII0WqG9Ag3tuWVwyT71lAmSnTYXexmborRsP/aEEJCEC6YEsaJ0HofqDNhi19S3cbrMHgQxcZ50bZrJ63alSRXJbZcm2BSebv43FufDKfftgMYIbjuKFY/hbFCy5Nd9XHaukYayeggWhLvhCzW54bqAenjw8EfqMcODOM7VF1pRglfibPoA47SuWTD8ig2bGYPdJW5ot8GBQEKJOjU8bD7Gl8yHdMA56jRjeWRTro+bTGypkYjHon1gPnRNmQNu8FRD7cBc0v/Y0jN2xjvWRTP3yvnf+5nz7wYkbmyaJIMvsr/OYqWPnqMHD5R0H4QsdByAawQMCN0CfhLATz645AItqD8FdH7bC1sFqCNKQwMwI4VICJ+VwGIsl4ikGcHhAR8y4eRJ2Y9N5x0H8hGnQD3FIG/5NiJL1TfDesi9BR+vJMP3FRyDU3x14DuybTZJNa7xCl3yrKvmSf0nnYZicwrlxeIhPGi/w+gDA2j6AHVlUeYYCcbzcMXGAhaMMWDLWAC6zDVoa/mnSZvjWBzNh60ANeHnj9igGo6AuMBgSMjunEBWZ8yh2JtvHf5MvOhaqjp0AgzDEZvDDfdC9bhP07fwAMl09QNZXbWgEreU4UOaeBkZijM2ja3wrbFr+NZj53H0Q7essyQY799k0yS9yJYtkkSoTu2JyOmsvwEvjL4+lDHgkacBBxcwR804yMgas6s/Bwx9mYcy2DNx0bBYuaDY5RdUcfOOYd+H692ZDd2ZIXcsAI2lzqrAcSbUj/VkMmYsWjII6vpjBFVzcb/70RBg1owFSHNhDPbD53x+HzrXvoBlRWR/o5NXSfb73DoRefgYij3wfBuecCgMXXg25+omsXSZeB+8vuQpanr0btHTSM+7sdizW6zzkWGxOmElKOGS6rwJ16gZ8DX3ld9UQRONRGB2N2kkIMQpGqm9gYABueTcJ2wZTcMNs9L61HNRFsnDllHa4d/s0z4gYk1j6mpMStux/yOzEMmwwkaqSBgizsaooagFPmUMTGxOG5iWNkKbBjHq6/4OD8Pq3HwPoT0FDfT1EIhHGg2sBGjAkWIODgzCwZS0Mfu8N6Lv4BsjO+zSaLBSgRAPsm3shTFz3K1dgnXVuKUWdLuIGpJctZkkKcj6E5x1AhtcoSdiFoNZWVUEMnQkaQFxt8rYEOD00Ffr94bbDcExdGi5qxevoWTh9fA88uasH2pNxVyDo+jlDsQHGR2EDR9RIxZIpqcAAxn7GojB+PKUqI+rEmadPYADiBAtS6CGvuesJ0AazUF1bSy/25YFLRNqAnp1+o9LX1wfKE3fBgB6G8MzFENIU6J98Ihze9DxEuvfmgekHrFSC+cXd8sIyCU6TKkSgRIB/lhuAPbEqGF1XR+8b2w/m9SZEdXU1e8h7txyCFVMzkNA1BvK5LYfhoa21noESFbUEqGHTi1ZD9oKDILFwmSSaNhzv2ZJg8jOIHw1IN18gVKVC06xRkFF09JY1eO93a0FL5mD02LFsgDtDuuJ1CWjqJyqRnh7ofupHoEw5AQGOQVZDTTB9CVT/+bcF7YJEtvhW516j10I7GchpasccNPM4icx+gzdcVVXDOoVuXmbfZZ1EHdidjMJvdybh8jmoDrUsnNLUD/dtSIImyU6x6zMJNqXNlGCN1ZXjZDEJzhq2BCs+Ekz33jivzpReQyPnA7Y//w5UIWB0H6RRnEkZGRDEmwZDqrsbUmufgfDilQzgVNMsSK75JdMkQYGVSrCbM+UFMHNmWN+ax29kB0GNJCCRSORJUZAwJ/cDXtyXgyvQhmPvwJi4ARNrDTiQcp+DqhpJcNaSYEp2uEtbEKJn0pDHkAQrnhKczWShsbUWnSiUXgR436Y9EEGNIvaBm20U66zpDDvu2roOQp+6GLtAgUx1LQB62aHB7oIwpIyf7Ddpwj8I0ExFh6LMESHakhpkN8kl1w9cp6omVf5eN9owRCusoyFEgZiUSMKevXKniUlwbsgGmwClsb50J4sAzmWHbLCC/3GHUKbiM+kM1E+oAg2dqxz6AAe2dhT0gR+4IjDM7BzYjTPNHORo1kFSHB8FyuH9BQNCdiwF2OkABQGXiNkWnTrXBPigoaPjMOQt+4Hq3CeAB8Ix+BCdlMk1WIfsx1WbUyunHbMHBZNgzQRYAXbtclQ0ES0HZhKsAgPZzTNnU0UcDYlR6AiqpopOdvbbjqWb9HqBTW2iOLPQB/vACFWBigM4F0vYz+QnvbIBoDvnd0HAJqJls0ocH1zVrGPVmh9niwbXBgx7tDeHoGkKk2BdK1zIx9uY82BBgpWcPWctxwYb3IsGE2CRpxOQbM4MY+bIwcKSGczYfLyAdQM5Z7rwEKLPRqP0UvIkCaa2YjGEIiTXBtgtveclyXY92SYLYHVQZwDJFugF3WdeNz6YgoUiAoaStqXbSeY1dOY9MzSUrH1uObFohc+DAay5cFr6TLwjyf7SfJw8aF3ThwI6HkkbcV+s49oqEq8GA/syixI8kEnlXd/ZXuQhS0nqzvSeMzUoNhKljcWiyTnSLC+XPVQubzT52WBpeozULk2VNBM01xQkXYd5V1yC6d2oTFmvzpipPYWpaC7BhpGSTqn4fWk0yNgUSWcOJ0+beqX+3OqYFkuMQoDjkEtnmQTnevbbzxTEqXJeUxdBDQJyXtaCbE0ewFnXEerMM8sS1Wxfs3hq1NepwmuK4NEoUMO2DUY3qSRg8wk1APJUmLYsXCGa16EGl2CNTdMU2TmStm7gskzUsfMhrJnSq2YMSHXsRFdHd7W5bmQ7WUGCAtJzqIQRDD1kAwxZ9/PdqOBcUrla2JJgskBZ6eAzG5ODFbFUNFUMlAiq+FyoYpGnGckaAljeoYYtwQxgj4Er6/yCAYDn1516DoSxL3OqAV27NuOYRRUdCbny8uvXPCfLK7fo3LJ2obCpptnN5a/L8swlSwYQV21M5SPAwADGB82lpWutmRqkXJQ9TSpU50EGmtPJYatN7FBlzuYpuz6ZKW6DSRmaizeMgu9nuAHrlN7aFZdBVeNk0DNZNgU8sOb3QnIn68lD9jwMYC+nxBMkakcSHDKzPqRWnU5OUA+a77NCKlo3AaaOU5SU630oKMGKypMNmZKcLPFcc3CozAbT6h8FfQDOzzn42bUoGaHwmYRmn8udLFkbWT1Jbu2Zl8CopZ+FUCZHb+XDofc3Q8/GNVCTSOQ5mcWoamaDuQvu9tCyjmUjikJwZIPDQxIsTg+CgFzAk6YpmqWiUZCxu0H29iOR+QK6YseiyePODkO60MjpQ9MkNWuHGwtAse6XSTDdLElwNme/CB9k3ktuemL2Ihh97mUQbTwGHyoLIZr7DvbD2w9+h6UZ+bP6geomycqcOXN24rbZDVg3gCkLVZNKQwq3ND1IRdFuxWMgW2ftBrB4zHlGc/1odpJsumTocYBwNchSmmx+nO1FuelnAYdQOA4D6SqWuCgH4FS6F6/dh/wzyCsGA/0xqKqqYr+3zqqBcJTCkioraZS2i687C6U9ju5dBF548lXo+rCHBT6ydA4OQNQB5tY6puCQXjcawpOmQmzmPNCr6hiwZkHV3tMDr95xA/Tv3gI1NTV2mLRYyeXE0oVeNsuts6gz2geS9pKWOHp+8bRuS7GfWnbWcYno6E1DMmlqlerqLFSpGenD0Ll9fRkspo2OxdKQSGRdEwOyOayTiE+yPwu9vabURiIp5BlhPKnNhV9sgYbxCcgYUQQsjuDFsIRx3/Siz7j0TNwPM7BTuB2EEAwaIUjiNmWVtKGzkgFzEBiUMTENPnSiWn7tzpshdWAvy7LRNcVATzGSawNMeckgXrMTDJIqnjUS32rwcqT8QObvNlGwngc+nLlUUVXSb5RqI6JBxlOf5cyDiQ9pAR4f5zyZKUNQNFTfhoIaxSCtYqpmVDV4Pu1rzC+gLUk4AZillCOQTbZcfbo3w0zRaIbCVsV07d4BG594EHY+9z8QjYShrq6O3QPXhsVOjfIAFiXYC2QvR4wF3nHEe0mvn10XiYMkC9o7zxXj1OUk+8VOEgcUt6nUT6lBvAaWDK3BRmjI59YjOlPJ6Dzgb2iDcxmmlrPmNNkKyNAeedbYP9kUJDu7YH/bTti7cT20r34JOrdshJCu24sA+IByPrsXkG7gMxuMndLs9sBeedyvnzAf4iFzTfN/t+2Adw51lgSwePzlM1qhqSHGprh/2tQBr2zc79r+1BNHw7JTxjEna8+BJDz4ix1lAzxlagLOvqCZTXkGU1n42Y83MaRoedH+/QfQJPTaTlQorMMvXrkXR5mpqm+/5rvw9mtv+16De9o8kSGucHEmNkqRWvE3JsFea6PdOpek6/RJk6Euyj4zDav2tIObPQ+yz3kumDIGZrXUMc23raMHnBpGVNETx8fgrCUT2ZRq045D8KOHNpWtohM1dbDktAlMAvuTWfjh999kPEk7RaMRU8NyD1UFNk0Ca5oUDkeYQ+Z3fSfA/OM13OYGBTOIo6XLkvN+QFNj5niQdxu2Vj+q+am9YgG2k9mqbkeycqDYtthJbPWFodihStMGQsmL7oZiyEPZJJyk2baegyEGMTLZNJsmgTVNopUc9fX1vktsRZBl91qO1Dp/193mmV4g85GmhHQWjybKWHNQt7ixn9NlDxp6aDYXJp6G63c/zPkpBYxDDGDK5si+N1IMmasdM+jQhsz3qZBPKjWYBwQHjzmXVqCDbLBiBTr4EuEgcWhZUsIPyGLB13WXNU9+ncQemuZoER7J0vIWiPs5aTKAWR1JpBYxw8zqUHRMdn85GIpFq2q4rHQhd65Uio5RLJpdQzMjWxZP50DLGVlLgjUTYEXNu1+/XHA5wAX9XXdLkHt1kh1vpUSDFaokyZOl6oIec54s5GmFKg1FzYvtikR1vf0ZO1RZW5soeEe5WKK2kWiYhSq5BLvxZFqMvs+ZpW7Ae0YTEauKey6Qdx4HTR6UA74qxlrdkvWuv4fNUCUrAfn4khWqZEXV3N1/5LWn47CVbAhD47h6iMdC/vx9aOzYOivZEDYHD7gPdnoLouvAYdBRijW816bmJl/+Yj+49W1RGPjw8X351Wt0mOCGWQEfT9y5ItBZb5PtZIXNdKDsHIu2bN9nBh1UWgsWg+OPm1AWuHSNmbMm2gBTkfWBuHqibWs7nqczkGedMCvPCXNrF0Qiy1XZdndyQ+9VeMrMWc9ShWGz0BITt/OC8LPTcnY2KWylC3Ou5YMPu+D99h5TihHks5fNzvsoajHFVM86LDpphi294RC9leB+D0Qb1m1GcDW2snLO/LkQr66y35vy67+g/VwKL15U8cUwv2KLPT8WJFgV+DjP8+OX5xzxbBIVwclyns+mLWivn3l+o62mz10xHxrqq31Vn1tZufJkqK5O2NIbDsehOhEvVHvClHD1n95A460wZ4sCFedcfL7r+UH71eu8oFjZhYcYiym8jRIassEsYyI5Lyh/tiaZpIJAtWww58n5OAvRo0++zIL9pFar4tVw0/V/xaZWbm3cSkvLWLjyqhVgvngWttV0Y2O9axuSkEOdXbDq+TXMBpMkX/j5i2D8hMZAz5vXP/jsF3zlOmiaMq2gz4rpR2dReYC/2MICGmR7raKGvM/lgQI/nmwObKloVR1qK2tPEtOxvwce+9UrthQvP3MBXHft+UU9y5w5U+Bf770WorEqWz2rFsizT2gtuDY/pr6j2PEjP36UBahpTlwVi8E/fO82GNc43vM5xeNYvAquuPk2WLbyUrjxngfg7EsvtxMvQfrNs3i9Oedl4JkE6UMrOnJW8EM2pXEjZySLhem4BKsUvFALgidiO57J+vadv4BlSxfCpAljWCjxqi+dC1OmTIS77vk17N69zzVaNHbsKLj88hVw0cWfYiaGX6Xn0GGoqUswD/S8C06D3zz5J5C8YmTf1873d8FDP34Err7hWrbSc+KkSfCd+/8NHv7hT+DlZ59z7RO693mnLYXPfOVaGNs0iX2nQ42E4FNnnw/P/fZJGBzoLzu2rpfyLo89Zw0PrejQrPShW+DED2g7vssdLNV898iLJw9OHD58GC7/yh3wX098F+rqqhnIy85YAKefdiKse3MrrH1zCwO6ty8J1VUxaG4eD/PmTYO5c1vNhQWMl/mq8wP3/xrWrt0EP/nprWyVyrRpLfAvd38dnn1mNby+5m1IJgfz7oEvRviPB34OU6dPh+XnnwM5dA4bGhrghn/6Jvz1V6+Bda+ugbZt2+HQwYPsnhvGjYfmY2fCcSctxoHUAGy1PUs4GbB/bzvccf3fQmogWdZ7VjbAbulCP4DZW4lCLDprpdScn0YshicLS/Jpkmp2OPEUlwLJ2tEAePe9XXD+yhvh5w/dDi3HmPNRsiKLFs1mhZ1rAUmUsyoMa9ufHIBbb/0hPPbo09hOhQ3rd8CcuTPoSeCUU+fDyacugMsvuwl2bN9dcH3WkXgPt1x/M3R1dsOlX/oirc1kPsS48ePg7JWfZfs5qy7H8sCqueTIMNdi0z28/vILcMeNX4OBvl6WtBiOP48gTfgHAYPNAyNDoUqSYOIle48oCOB8Xsm8Z80KP2rhgq8DyNrxl8zbdnbAGWddDV+//gq46sqV6BGbiwEMe8GylW+n+7H6dQAl8le/fgbuufth2L//ENTW1rJTr7v22/Do43dDc8tEBgS9JkNv/zuX0IiDjLTJ9277Drz0/Itww83fgGnHHUerrFl+2GAAKxYv89gccAps3fgOPHzvPfDSH//AbDoteKC+LCczZgNcqg1m781iu0GrbTqXs5fveJEXUNQ+haI1mDNRSHt8oljkxVU1dU4ymYTbbr8P7v7BI3DeeUth6RknwezZx0Jj03ic14ZYMmF3+x748/rN8NKLr8Mzf3wJenp6WYfSi2O0pevt23cQzlnxZfSsL0M7fBYc0zIZB8MAywvLYuPUhsAnHmtWvQorl58L8xYsgKUrlsMJCxZC85SpOOWqYSOsu6sbtr23Bd56bQ28/H/PwuYN69kA4W/8E/9yFg/m9dHs2bPtRXfFAEyqs6enh3UoX2ZDasUPYDewOcDEs7+/31qTVc34BrHrXKvQwCMQ6P74dMkcIOYgoPCimI/l7/9Sx/LlOfz56NMKxIt/K4ukm5YIueXPecCEf3+EttzxFNWtndiwljqJCX/n257lkl7KMhfemXzUcVUi+/JNMUSdwHnyYIaX/ZURl2Tiw+ePzsXrYuc6E+78emwhofUZCvGDrbIv7jiJ59hpy+evYmqQDzDn9XkfDCfppXi9fATyTuEdUq7N4KCSmuM8S33flzp3KImfH9t1Rs9k/MXlNLzTxYiSsz9k7amteA8iyZI8I0Gu6cIgJPvASDkSLHYiJ9n7y8Xy8yK/e+aDzu1+/MjZvpR7KId0vw44EqmcNVkjxfvjouL18xFAIyUNRyLpwzGZrtAnl3S+mr9CRyeVNE2q0JFBbCpbVVU1qWKzjk5iAONW8VpNX6Ejl6y5/FHpSFcI7L9lpbOYa4WOLiL1TLF8Et/+aDQar9jho4t4rkDv6ek5EI/Hm9lHqSve9FFDFAenbJa+Z88emDlzJquo0NFDlFFrb29nEszWNFEF5WErUnzkE/+0xr59+8xY9K5du+D4448XkuMVOpKJ0q2EKftDYVRB9pfQHj16NJPmihQfmUSOFS1SoFU2HR0drE7nyWZCnL7LRMtu6IQKHXnEv/Hx7rvvsuO8twtJNW/ZsoVNjvlKhAodGSQuOty+fXuegGqI8g1Y2FpRssGkohsbGxn6sr8YUqFPHpFTRUGNnTt3wv79Q3/fwVyGrGltuD9ZbECqesaMGfbqwIpN/mQSD2ZwcGnKW/AFBTxhE25nOhtTIwKZGpBUF7u6sUIjS4QLYUTmlNQyOcm8Pu88POE5tL/LZAxI9KdPn84kmq8RPhrXcB1JRL4SV8mkYclv6u3tzTtH+ETEgIJzpp+irf0bJyNxJIwbNw4mT57MwKVgCIFdccI+eqL5LX+5YO/evUwty+IWwiefNtGH0N7yUr90Mon/wYMHoampiTlgJNG08p99v9F6tWQk1/b+pZG4jJZUMH8lhoiw2L17N9OmRF5fMULzu15B6Ty+u7t7A0CQv9dt5hjp1cgxY8bAqFGj7LCY6HG7fblHtuBc9lsQHl5fnnH7ko2sE52f1Xf+VmqRfUeDS5vbNzbED7jwhfckfIgP844JXK+ZjfPLOzgv/juqUROJxDZs2FLsSCMmFDkhe8DfUgza0cUAUww/8UGdW5mkuG396twGiFd9kLb8mDQjmUKyr17hYzcJRgHJjh49eir7g9SoAn6JTG4uFmAimlTzifVI2uW8r+EFOHc4KMjzFPPMfufmvQiv5P/BrGKeleoQ09VtbW07WSwapfBBlOCbEOSy1u+MtONVjAf/UYAcdMA5eck+i1gsL6/nxDoDbfb9bJ9Xoi1+HA3350eqM0qlYh56JJy84fog2XCT27NSPdruHQcOHKDPE6RtiUUp/meU4s+iFEdH4oa8Pkk4nKN3JGm4VfZwPqvwu4FY3grsz1U7POdJkyZ9C+3pP0IAj5qD4qZ2PsqHK6WtbFANpz0dSfISimg0+nx7e/uZYH1+xHlGCEF+Bee3Cz+2u/d5MKJSJX44qBxgxft2+652qX1ChFOrg+hcnUjOFa9zOlVpPOkSPOk1nH+NG8lOKhcscRSPFODlSqkboEGeqdi+wJLBqeoXduzYsTPvN1mDlpaWhQjw/6I9rh2pjhppCQzyVR9+3kiYmeFW4V7Pg79lUSiv2b59+08LfnNr1NraejI6Xb/DGx3t9yDFjFK3mx8ulfVx0Edhjz2kO41e898juA9I23kxRUmejgz/ExnP8ju3QsHITQWLWiQo4bmHcENq+feu5/gxwflxVU1NzZ2orq8G84++VujjJwPBfQE17JWiQyWjwMNl6tSpp6iqeieOtMXFtPs4yfkdLrHOy+6Wa3JGkOiG2rB8c9u2bY9bx959UOwVpkyZsgx1/rW4ex6WiGEYn0iw3ea4QcAbyTl9iUTZhtV4X/dv2bLll2AFMQL1Q6lXbG5uHoVu+Qq86FLsjBNxOx2raz7unjgaCPtzAPtzB+6uR9O4ClXx036q2I3+H6KpdSN3OOzWAAAAAElFTkSuQmCC"


class Broadcaster():
    def __init__(self, config, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.event_loop = asyncio.get_event_loop()

    async def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        
        self.sock.bind((self.config['IP'], 0))        
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(False)
        
        self.logger.info("Starting broadcast loop")
        await self.loop() # Start the loop broadcast task

    async def loop(self):
        while True:
            self.logger.debug("Sending broadcast")
            await self.event_loop.sock_sendto(self.sock, UPNP_BROADCAST.encode(), (self.config['BCAST_IP'], self.config['UPNP_PORT']))
            await asyncio.sleep(self.config['BROADCAST_INTERVAL'])

    async def stop(self):
        self.logger.debug("Stopping broadcast loop")
        await asyncio.to_thread(self.sock.close)

class Responder():
    def __init__(self, config, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.event_loop = asyncio.get_event_loop()

    async def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', self.config['UPNP_PORT']))
        mreq = struct.pack("4sl", socket.inet_aton(
            self.config['BCAST_IP']), socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        self.sock.setblocking(False)

        # Issue 9: create separate response socket bound to assigned interface
        self.sockresp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sockresp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sockresp.bind((self.config['IP'], self.config['UPNP_PORT']))
        self.sock.setblocking(False)

        self.logger.info("Starting response loop")
        await self.loop() # Start the loop response task

    async def loop(self):
        while True:
            try:
                self.logger.debug("Waiting for M-SEARCH")
                data, addr = await self.event_loop.sock_recvfrom(self.sock, 1024)
                data = data.decode() # type: ignore
            # if socket closed by stop() method
            except ConnectionResetError:
                break
            except socket.error as e:
                if e.winerror == 995:
                    break
                else:
                    self.logger.error(e)
                    continue
            else:
                if M_SEARCH_REQ_MATCH in data:
                    self.logger.debug("Received M-SEARCH from {}".format(addr))

                    if "urn:schemas-upnp-org:device:basic:1" in data:
                        self.logger.debug("received urn:schemas-upnp-org:device:basic:1")
                        
                        resp = UPNP_RESPOND_TEMPLATE.format(
                            self.config['IP'],
                            self.config['HTTP_PORT'],
                            "urn:schemas-upnp-org:device:basic:1",
                            self.config['SERIALNO'])

                        await self.event_loop.sock_sendto(self.sockresp, resp.encode(), addr) # type: ignore
                        #self.logger.debug("Response sent: "+resp)
                    elif "upnp:rootdevice" in data:
                        self.logger.debug("received upnp:rootdevice")
                        resp = UPNP_RESPOND_TEMPLATE.format(
                            self.config['IP'],
                            self.config['HTTP_PORT'],
                            "upnp:rootdevice",
                            self.config['SERIALNO']
                        )
                        await self.event_loop.sock_sendto(self.sockresp, resp.encode(), addr) # type: ignore
                        #self.logger.debug("Response sent: "+resp)
                    elif "ssdp:all" in data:
                        self.logger.debug(
                            "received ssdp:all responding with upnp:rootdevice")
                        resp = UPNP_RESPOND_TEMPLATE.format(
                            self.config['IP'],
                            self.config['HTTP_PORT'],
                            "upnp:rootdevice",
                            self.config['SERIALNO']
                        )
                        await self.event_loop.sock_sendto(self.sockresp, resp.encode(), addr) # type: ignore
                        #self.logger.debug("Response sent: "+resp)
                    else:
                        self.logger.debug("ignoring")
                    self.logger.debug("----------------------")
                    self.logger.debug("  ")

    async def stop(self):
        self.logger.debug("Stopping response loop")
        await asyncio.to_thread(self.sock.close)
        await asyncio.to_thread(self.sockresp.close)


class Httpd():
    def __init__(self, devices, config, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.devices = devices

        self.event_loop = asyncio.get_event_loop()

    async def run(self):
        try:
            self.logger.info("Starting HTTP server on {IP}:{HTTP_PORT}".format(**self.config))

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.config['IP'], self.config['HTTP_PORT']))
            self.sock.listen(100)
            self.sock.setblocking(False)

            await self.loop()

        except socket.error as msg:
            self.logger.error("Http Socket Error: {}".format(msg))

    async def loop(self):
        while True:
            try:
                client, addr = await self.event_loop.sock_accept(self.sock)
            except ConnectionResetError:
                break
            # if socket closed by stop() method [WinError 995] Der E/A-Vorgang wurde wegen eines Threadendes oder einer Anwendungsanforderung abgebrochen
            except socket.error as e:
                if e.winerror == 995:
                    break
                else:
                    self.logger.error(e)
                    continue
            else:
                self.logger.debug("Received connection from {}".format(addr))
                self.event_loop.create_task(self.handle(client, addr))

    async def handle(self, client:socket.socket, addr):
        try:
            
            # all data isnt always sent right away--try a couple more times
            # 2015-08: Logitech change the data flow slightly.  We seem to need to
            # return the payload for "GET /api/lights" sooner.  The 1 sec sleeps
            # have been removed and we only do another "request.recv" if the
            # content-length is found and greater than 0
            # 2015-10: Header size is now computed to determine exactly how much
            # data still needs to be pulled
            data = ""
            for i in range(3):
                data += (await self.event_loop.sock_recv(client, 1024)).decode()
                if "\r\n\r\n" in data:
                    break
        except socket.error:
            self.logger.error("Socket error")
        else:
            if not data:
                self.logger.debug("Connection closed by {}".format(addr))
            else:
                self.logger.debug("Received data from {}: {}".format(addr, data))
                await self.handle_request(client, data)
                client.close()


    async def handle_request(self, client, data):
        if "test" in data:
            await self.event_loop.sock_sendall(client, "ok".encode())
            return

        searchObj = re.search(r'content-length: (\d+)', data, re.I)
        if searchObj and int(searchObj.group(1)) > 0:
            contentLength = int(searchObj.group(1))
            headerLength = data.find("\r\n\r\n") + 4
            self.logger.debug("Header-Length={} Content-Length={}".format(headerLength, contentLength))
            # got the header--now grab the remaining content if any
            #if len(data) < headerLength + contentLength:
                #data += client.recv(headerLength + contentLength - len(data)).decode() #Cause of problem maybe?
        else:
            contentLength = 0

        self.logger.debug("Content-Length={}".format(contentLength))

        if "description.xml" in data:
            # send description.xml and end for get request
            await self.event_loop.sock_sendall(client, DESCRIPTION_XML.encode())
            self.logger.debug("{} Sent HTTP description.xml Response".format(client))
            # alexa discovery request
            self.logger.debug("Alexa, discover devices")

        elif "hue_logo_0.png" in data:
            await self.event_loop.sock_sendall(client, ICON_HEADERS.encode())
            await self.event_loop.sock_sendall(client, ICON_SMALL.decode('base64').encode())
        elif "hue_logo_3.png" in data:
            await self.event_loop.sock_sendall(client, ICON_HEADERS.encode())
            await self.event_loop.sock_sendall(client, ICON_BIG.decode('base64').encode())

        elif re.match(r'GET /api/.*lights ', data, re.I):
            resp = "\n{"
            i = 1
            for device in self.devices:
                # TODO: Force update of device? dst = device.st()
                resp += "\"%d\":" % (i)
                resp += await self.get_onelight_json(device)
                if i < len(self.devices):
                    resp += ","
                i += 1
            resp += "}\n"
            await self.send_json(client, resp)

        elif "PUT /api" in data:
            matchObj = re.match(r'PUT /api/(.*)lights/(\d+)/state', data, re.I)
            # if "/lights/" in data and "/state" in data:
            if matchObj:
                self.logger.debug("{} Got PUT request to do something".format(client))
                # reqId is what Alexa passes, the match will include the trailing / for now.
                reqId = matchObj.group(1)
                reqHueNo = matchObj.group(2)
                # Just the content
                # Examples:
                #   Harmony: {"on":true,"bri":254}
                #   Echo: {"on": true}
                self.logger.debug("%s Content data=---\n%s\n---" % (client, data[-contentLength:]))

                parsedContent = json.loads(data[-contentLength:])

                self.logger.debug("%s Parsed Content data=---\n%s\n---" % (client, str(parsedContent)))
                #
                # Update the specified device
                #

                deviceNum = int(reqHueNo) - 1

                self.logger.debug("device number:%d" % deviceNum)
                device = self.devices[deviceNum]

                erg = await device.set(parsedContent)

                await self.send_json(client, json.dumps(erg))

            # All other PUT /api/ send back a blank response
            else:
                await self.send_json(client, "")

        # Requesting the state of just one light
        elif re.match(r'GET /api/.*lights/(\d+) ', data, re.I):
            self.logger.debug("{} Got request for one light".format(client))
            reqHueNo = "1"
            matchObj = re.match(r'GET /api/.*lights/(\d+) ', data, re.I)
            if matchObj:
                reqHueNo = matchObj.group(1)
            device_num = int(reqHueNo) - 1
            device = self.devices[device_num]
            # TODO: Force update of device? dst = device.st()
            OneResp = await self.get_onelight_state_json(device)
            await self.send_json(client, OneResp)

        # Assuming this is a new device registration or config request
        elif "GET /api" in data:
            if "/config" in data:
                self.logger.debug("{} Got request for /config".format(client))
                await self.send_json(client, APICONFIG_JSON)
                self.logger.debug("{} Sent API Config".format(client))
            else:
                newDev = "newdeveloper"
                matchObj = re.match(r'GET /api/(.+) ', data, re.I)
                if matchObj:
                    newDev = matchObj.group(1)
                self.logger.debug("{} Got request for new dev: {}".format(client, newDev))
                json_resp  = """{"lights":{"""
                i = 1
                for device in self.devices:
                    json_resp += """"%d":""" % (i)
                    json_resp += await self.get_onelight_json(device)
                    if i < len(self.devices):
                        json_resp += ","
                    i += 1

                json_resp += """},"schedules":{"1":{"time":"2012-10-29T12:00:00","description":"","name":"schedule","command":{"body":{"on":true,"xy":null,"bri":null,"transitiontime":null},"address":"/api/newdeveloper/groups/0/action","method":"PUT"}}},"config":{"portalservices":false,"gateway":"%s","mac":"%s","swversion":"01005215","linkbutton":false,"ipaddress":"%s:%s","proxyport":0,"swupdate":{"text":"","notify":false,"updatestate":0,"url":""},"netmask":"255.255.255.0","name":"Philips hue","dhcp":true,"proxyaddress":"","whitelist":{"newdeveloper":{"name":"test user","last use date":"2015-02-04T21:35:18","create date":"2012-10-29T12:00:00"}},"UTC":"2012-10-29T12:05:00"},"groups":{"1":{"name":"Group 1","action":{"on":true,"bri":254,"hue":33536,"sat":144,"xy":[0.346,0.3568],"ct":201,"alert":null,"effect":"none","colormode":"xy","reachable":null},"lights":["1","2"]}},"scenes":{}}\n""" % (self.config['GATEWAYIP'], self.config['MACADDRESS'], self.config['IP'], self.config['HTTP_PORT'])
                await self.send_json(client, json_resp)
                self.logger.debug("{} Sent HTTP New Dev Response".format(client))

        # I only saw a POST when registering the username
        elif "POST /api" in data:
            await self.send_json(client, NEWDEVELOPERSYNC_JSON)
            self.logger.debug("{} Sent HTTP New Dev Sync Response".format(client))
        else:
            await self.event_loop.sock_sendall(client, "HTTP/1.1 404 Not Found".encode())

        self.logger.debug("-------------------------------")
        self.logger.debug("    ")

    async def get_onelight_json(self, device):
        # example template values: "on", "[0.0,0.0]", "Hue Lamp 1", "254", "201"
        # on, bri, xy, ct, name
        data = await self.get_json_att(device, ALL)
        data["uniqueid"] = self.gen_unique_id()
        return json.dumps(data)
    
    def gen_unique_id(self):
        # gen "00:11:22:33:44:55:66:77-88" like id
        serial = uuid.uuid4().hex[:18]
        return ":".join([serial[i:i+2] for i in range(0, len(serial)-2, 2)]) + "-" + str(serial[-2:])

    async def get_onelight_state_json(self, device):
        # example template values: "on", "[0.0,0.0]", "Hue Lamp 1", "254", "201"
        # on, bri, xy, ct, name
        return json.dumps(await self.get_json_att(device, GETSTATE))

    async def get_json_att(self, device, template):
        json_resp = copy.deepcopy(template)

        json_resp["state"]["on"] = device.on
        json_resp["state"]["hue"] = device.hue
        json_resp["state"]["sat"] = device.sat
        json_resp["state"]["bri"] = device.bri
        json_resp["state"]["ct"] = device.ct
        json_resp["state"]["xy"] = device.xy
        json_resp["state"]["colormode"] = device.colormode
        json_resp["name"] = device.name
        json_resp["swupdate"]["lastinstall"] = datetime.datetime.now().isoformat().split(".")[0]

        return json_resp

    async def send_json(self, client, resp):
        date_str = email.utils.formatdate(timeval=None, localtime=False, usegmt=True)
        full_resp = (JSON_HEADERS %(len(resp), date_str, resp)).replace("\n", "\r\n")
        await self.event_loop.sock_sendall(client, full_resp.encode())

    async def stop(self):
        self.logger.debug("Stopping HTTP Server")
        await asyncio.to_thread(self.sock.close)

#
# This is the main object which all other handlers inherit from:


class hue_upnp_super_handler(object):
    def __init__(self, name, id, logger, on=False, bri=1):
        self.name = name
        self.id = id
        self.logger = logger

        self.on = on
        self.bri = bri

        self.get_default()

    # Set default initial values
    # Can be overridden, or used as a super, or just use the defaults.
    def get_default(self):
        self.xy = [0.0, 0.0]
        self.ct = 199
        self.hue = 0
        self.sat = 254
        self.colormode = "ct"

    # Super set method, parses incomming data and runs the appropriate method.
    async def set(self, data):
        results = []
        
        for elm in data:
            match (elm):
                case 'on':
                    self.logger.debug("on received: {}".format(data['on']))
                    if data['on']:
                        ret = await self.set_on()
                    else:
                        ret = await self.set_off()
                case 'bri':
                    self.logger.debug("bri received: {}".format(data['bri']))
                    ret = await self.set_bri(data['bri'])
           
                case 'ct':
                    self.logger.debug("ct received: {}".format(data['ct']))
                    if (ret := await self.set_ct(data['ct'])):
                        self.colormode = "ct"

                case 'xy':
                    self.logger.debug("xy received: {}".format(data['xy']))

                    if (ret := await self.set_xy(data['xy'])):
                        self.colormode = "hs"

                case 'hue':
                    self.logger.debug("hue received: {}".format(data['hue']))

                    if (ret := await self.set_hue(data['hue'])):
                        self.colormode = "hs"

                case 'sat':
                    self.logger.debug("sat received: {}".format(data['sat']))

                    if (ret := await self.set_sat(data['sat'])):
                        self.colormode = "hs"

                case _: # default
                    self.logger.error("ERROR: Unknown command: {}".format(elm))
                    ret = False

            if ret:
                results.append({"success": {f"/lights/{self.id+1}/state/{elm}": data[elm]}})
            else:
                results.append({"error": {"type": 901, "address": f"/lights/{self.id+1}/state/{elm}", "description": "Internal error"}})

        return results

    # Default, should always be overridden
    async def set_on(self):
        self.logger.error("ERROR: Device " + self.name + " does not have an on command?")

    # Default, should always be overridden
    async def set_off(self):
        self.logger.error("ERROR: Device " + self.name +" does not have an off command?")

    # Default, should always be overridden
    async def set_bri(self, value):
        self.logger.error("ERROR: Device " + self.name + " does not have a bri command?")

    # Default, should always be overridden
    async def set_ct(self, value):
        self.logger.error("ERROR: Device " + self.name + " does not have a ct command?")

    # Default, should always be overridden
    async def set_xy(self, value):
        self.logger.error("ERROR: Device " + self.name + " does not have a xy command?")

    # Default, should always be overridden
    async def set_hue(self, value):
        self.logger.error("ERROR: Device " + self.name + " does not have a hue command?")

    # Default, should always be overridden
    async def set_sat(self, value):
        self.logger.error("ERROR: Device " + self.name + " does not have a sat command?")


class Device(hue_upnp_super_handler):
    def __init__(self, name:str, on = False, bri = 1) -> None:
        self.id = None
        self.name = name
        super().__init__(self.name, None, None, on, bri if bri <= 254 and bri >= 1 else 1)

    def init(self, id, logger):
        self.logger = logger
        self.id = id

    async def set_on(self):
        self.logger.debug(f"Device: {self.name} set ON!")

        if await self.on_on() != False:
            self.on = True
            return True
        return False

    async def set_off(self):
        self.logger.debug(f"Device: {self.name} set OFF!")

        if await self.on_off() != False:
            self.on = False
            return True
        return False

    async def set_bri(self, value):
        self.logger.debug(f"Device: {self.name} set BRI {self.bri}!")

        if await self.on_bri(value) != False:
            self.bri = value
            return True
        return False

    async def set_ct(self, value):
        self.logger.debug(f"Device: {self.name} set CT {self.ct}!")

        if await self.on_ct(value) != False:
            self.ct = value
            return True
        return False

    async def set_xy(self, value):
        self.logger.debug(f"Device: {self.name} set XY {self.xy}!")

        if await self.on_xy(value) != False:
            self.xy = value
            return True
        return False

    async def set_hue(self, value):
        self.logger.debug(f"Device: {self.name} set HUE {self.hue}!")

        if await self.on_hue(value) != False:
            self.hue = value
            return True
        return False

    async def set_sat(self, value):
        self.logger.debug(f"Device: {self.name} set SAT {self.sat}!")

        if await self.on_sat(value) != False:
            self.sat = value
            return True
        return False

    async def on_on(self):
        return True

    async def on_off(self):
        return True

    async def on_bri(self, value):
        return True
    
    async def on_ct(self, value):
        return True
    
    async def on_xy(self, value):
        return True

    async def on_hue(self, value):
        return True
    
    async def on_sat(self, value):
        return True
    

class Hub(AbstractAsyncContextManager):
    def __init__(self, debug = False) -> None:
        self.devices = []
        self.config = {}

        self.setup_debug(debug)
        self.gen_config()

    def gen_config(self):
        self.config["GATEWAYIP"] = "1.1.1.1"
        self.config["HTTP_PORT"] = 80 # only port 80 is supported
        self.config["BCAST_IP"] = "239.255.255.250"
        self.config["UPNP_PORT"] = 1900 # type: ignore
        self.config["BROADCAST_INTERVAL"] = 200 # type: ignore

        self.gen_uuids()

    def gen_uuids(self):
        serial = uuid.uuid4().hex[:12].upper()
        
        self.config["MACADDRESS"] = ":".join([serial[i:i+2] for i in range(0, len(serial), 2)])
        self.config["SERIALNO"] = serial

    def get_ip(self):
        try:
            self.logger.debug("Retrieving local IP address...")
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            try:
                s.connect(('10.254.254.254', 1))
                ip = s.getsockname()[0]
            except:
                ip = "127.0.0.1"
            finally:
                s.close()

            self.logger.debug("Local IP address is: {}".format(ip))

            if ip != "127.0.0.1":
                return ip
            else:
                self.logger.exception("No valid IP address found.")
        except socket.error as e:
            self.logger.exception("Failed to retrieve local IP address: {}".format(e))


    def setup_debug(self, debug):
        self.logger = logging.getLogger("AlexaHue")
        if debug is True:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
        consoleHandlerDebug = logging.StreamHandler(sys.stdout)
        consoleHandlerInfo = logging.StreamHandler(sys.stdout)
        consoleHandlerError = logging.StreamHandler(sys.stdout)
        #change color of debug messages
        consoleHandler = logging.StreamHandler(sys.stdout)
        consoleHandlerDebug.addFilter(lambda record: record.levelno == logging.DEBUG)
        consoleHandlerDebug.setFormatter(logging.Formatter(
            "\033[1;30m%(asctime)s [Alexa Hue Emulation] [%(levelname)-5.5s] %(message)s\033[0m"))
        #change color of info messages
        consoleHandlerInfo.addFilter(lambda record: record.levelno == logging.INFO)
        consoleHandlerInfo.setFormatter(logging.Formatter(
            "\033[1;32m%(asctime)s [Alexa Hue Emulation] [%(levelname)-5.5s] %(message)s\033[0m"))
        #change color of error messages
        consoleHandlerError.addFilter(lambda record: record.levelno == logging.ERROR)
        consoleHandlerError.setFormatter(logging.Formatter(
            "\033[1;31m%(asctime)s [Alexa Hue Emulation] [%(levelname)-5.5s] %(message)s\033[0m"))
        
        consoleHandler.addFilter(lambda record: record.levelno != logging.DEBUG and record.levelno != logging.INFO and record.levelno != logging.ERROR)
        
        self.logger.addHandler(consoleHandlerDebug)
        self.logger.addHandler(consoleHandlerInfo)
        self.logger.addHandler(consoleHandlerError)
        self.logger.addHandler(consoleHandler)

        
    def add(self, *devices: list[Device]):
        for device in devices:
            self.logger.debug('Adding device: ' + device.name)
            device.init(len(self.devices), self.logger)
            self.devices.append(device)

    async def run(self):
        global UPNP_BROADCAST, DESCRIPTION_XML, APICONFIG_JSON
        # same as the MACADDRESS with colons removed
        # Put our info in the responses
        if self.config.get("IP") is None:
            self.config["IP"] = self.get_ip()

        UPNP_BROADCAST = UPNP_BROADCAST.format(self.config['IP'], self.config['HTTP_PORT'], self.config['SERIALNO'])
        DESCRIPTION_XML = DESCRIPTION_XML.format(self.config['IP'], self.config['HTTP_PORT'], self.config['IP'], self.config['SERIALNO'], self.config['SERIALNO'])
        APICONFIG_JSON = APICONFIG_JSON % (self.config['MACADDRESS'])

        self.responder = Responder(self.config, self.logger)
        self.broadcaster = Broadcaster(self.config, self.logger)
        self.httpd = Httpd(self.devices, self.config, self.logger)

        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.responder.run())
            tg.create_task(self.broadcaster.run())
            tg.create_task(self.httpd.run())

    async def stop(self):
        self.logger.debug("Stopping hub...")
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self.responder.stop())
                tg.create_task(self.broadcaster.stop())
                tg.create_task(self.httpd.stop())
        except Exception as e:
            self.logger.exception("Failed to stop hub: {}".format(e))
        self.logger.debug("Hub stopped.")

    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()
    


async def test():
    async with Hub(True) as hub:
        hub.add(Device('Test Device', True, 254))
        await hub.run()

if "__main__" == __name__:
    asyncio.run(test())
