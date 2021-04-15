import os
import re
import sys

import copy
import datetime

import collections.abc

from construct import *

# All specifications pertain to replay version 0x59

# Dirty hack to avoid failing to parse replays with broken UTF-8 player names
import codecs
codecs.register_error("strict", codecs.ignore_errors)

ENC = "ascii"
ENC_2 = "utf-8"

ENTITY_LOOKUP = {}
PREFAB_LOOKUP = {}

ENTITY_TYPES = {
    0x00: "WorldSpawn",
    0x01: "PlayerSpawn",
    0x02: "Player",
    0x03: "PointLight",
    0x04: "Projectile (Grenade)",
    0x05: "Projectile (Rocket)",
    0x06: "Projectile (Plasma)",
    0x07: "Projectile (Burstgun)",
    0x08: "Projectile (Stake)",
    0x09: "Teleporter",
    0x0A: "Target",
    0x0B: "JumpPad",
    0x0C: "Effect",
    0x0D: "Pickup",
    0x0E: "ChatMessage",
    0x0F: "CameraPath",
    0x10: "Vote",
    0x11: "Damage",
    0x12: "RaceStart",
    0x13: "RaceFinish",
    0x14: "WeaponRestrictor",
    0x15: "Prefab",
    0x16: "VolumeSelect",
    0x17: "WorkshopScreenshot",
    0x18: "ReflectionProbe",
    0x19: "TriggerVolume",
    0x1A: "Message",
    0x1B: "Goal",
    0x1C: "Turret",
    0x1D: "Shootable",
    0x1E: "Accumulator",
    0x1F: "Exit",
    0x20: "NavLink",
}

# TODO: Create mutatorMask primitive
# TODO: Create votesMask primitive

# Additional primitives
def HexBytes(len): # Used for transparently displaying bytes I don't know the meaning of
    return Hex(BytesInteger(len))


def camera_path_field_stuff(m):
    # TODO: Maybe only one of x40 and x80, who knows :) :)
    # Absolutely cannot be bothered reversing this more
    if m.x4 or m.x40 or m.x80:
        return True

    return False


Mask8 = FlagsEnum(Byte, x1=0x01, x2=0x02, x4=0x04, x8=0x08, x10=0x10, x20=0x20, x40=0x40, x80=0x80)

InputMask = FlagsEnum(Byte, fwd=0x01, back=0x02, left=0x04, right=0x08, jump=0x10, x20=0x20, crouch=0x40, x80=0x80)

Bool8 = ByteSwapped(Aligned(4, Flag))


Vector2 = Struct(
    "x" / Float32l,
    "y" / Float32l
)


Vector3 = Struct(
    "x" / Float32l,
    "y" / Float32l,
    "z" / Float32l
)


ColorARGB32l = Struct(
    "b" / Int8ul,
    "g" / Int8ul,
    "r" / Int8ul,
    "a" / Int8ul
)


ColorXRGB32l = Struct(
    "b" / Int8ul,
    "g" / Int8ul,
    "r" / Int8ul,
    "x" / Int8ul
)


ViewAngle32l = Struct(
    "x" / Int16ul,
    "y" / Int16sl,
)


Face = Struct(
    "index" / Int8ul,
    "numEdges" / Int8ul,
    "unknown1" / Int16ul,
    "offsetX" / Float32l,
    "offsetY" / Float32l,
    "scaleX" / Float32l,
    "scaleY" / Float32l,
    "rotation" / Float32l
)


PrefabBrush = Struct(
    "numVertices" / Int8ul,
    "numFaces" / Int8ul,
    "numEntriesFaceTable" / Int8ul,
    "lenMaterialColorArrays" / Int8ul,
    "lenMaterialArrayBytes" / Int32ul,
    "unknown1" / Int32ul, # TODO: This might be boundEntityIdDivBy2
    "unknown2" / Int32sl,
    "vertices" / Array(this.numVertices, Vector3),
    "faces" / Array(this.numFaces, Face),
    "faceTable" / Array(this.numEntriesFaceTable, Int8ul),
    "materials" / Array(this.lenMaterialColorArrays, CString(ENC)),
    "colors" / Array(this.lenMaterialColorArrays, ColorXRGB32l),
)


Brush = Struct(
    "brushId" / Int32ul,
    "unknown1" / Int8ul, # Maybe something like numSubBrushes?
    "numVertices" / Int8ul,
    "numFaces" / Int8ul,
    "numEntriesFaceTable" / Int8ul,
    "lenMaterialColorArrays" / Int8ul,
    "lenMaterialArrayBytes" / Int32ul,
    "entityIdAttachedTo" / Int32ul,
    "unknown2" / Int32sl,
    "vertices" / Array(this.numVertices, Vector3),
    "faces" / Array(this.numFaces, Face),
    "faceTable" / Array(this.numEntriesFaceTable, Int8ul),
    "materials" / Array(this.lenMaterialColorArrays, CString(ENC)),
    "colors" / Array(this.lenMaterialColorArrays, ColorXRGB32l),
)


PrefabEntity = Struct( # A lot of shortcuts taken here, but I don't wanna bother elaborating on this
    "numBrushes" / Int32ul,
    "entityType8" / Int8ul,
    "entityType32" / Int32ul,
    "unknown1" / Int32sl, # Seems to be constant FFFFFFFF, so I'll assume it's signed and means -1
    "entity" / Switch(this.entityType8, {
        0x00: Struct( # WorldSpawn
            "position" / Vector3,
            "angles" / Vector3,
            "targetGameOverCamera" / PaddedString(32, ENC),
            "sky.timeOfDay" / Float32l,
            "sky.skyAngle" / Float32l,
            "sky.skyTopColor" / ColorXRGB32l,
            "sky.skyHorizonColor" / ColorXRGB32l,
            "sky.skyBottomColor" / ColorXRGB32l,
            "sky.skyTopColorIntensity" / Float32l,
            "sky.skyHorizonColorIntensity" / Float32l,
            "sky.skyBottomColorIntensity" / Float32l,
            "sky.sunColor" / ColorXRGB32l,
            "sky.sunIntensitySize" / Float32l,
            "sky.sunSharpness" / Float32l,
            "sky.sunEnabled" / Bool8, # Bool8
            "sky.horizonColor" / ColorXRGB32l,
            "sky.horizonIntensity" / Float32l,
            "sky.horizonHaloExponent" / Float32l,
            "sky.horizonHaloExponentSun" / Float32l,
            "sky.horizonHaloExponentSunIntensity" / Float32l,
            "sky.horizonLine" / Float32l,
            "sky.starsIntensity" / Float32l,
            "sky.cloudsColor" / ColorXRGB32l,
            "sky.cloudsCoverage" / Float32l,
            "sky.cloudsSpeed.x" / Float32l,
            "sky.cloudsSpeed.y" / Float32l,
            "sky.cloudsCoverageMultiplier" / Float32l,
            "sky.cloudsBias" / Float32l,
            "sky.cloudsRoughness" / Float32l,
            "sky.cloudsDensity" / Float32l,
            "sky.cloudsThickness" / Float32l,
            "colorTeamA" / ColorXRGB32l,
            "colorTeamB" / ColorXRGB32l,
            "fogColor" / ColorXRGB32l,
            "fogDistanceStart" / Float32l,
            "fogDistanceEnd" / Float32l,
            "fogHeightTop" / Float32l,
            "fogHeightBottom" / Float32l,
            "title" / PaddedString(256, ENC),
            "ownerString" / PaddedString(256, ENC),
            "playersMin" / Int8ul,
            "playersMax" / Int8ul,
            "modeCTF" / Flag, # TODO: Implement padding / alignment
            "modeFFA" / Flag, # TODO: Implement padding / alignment
            "modeTDM" / Flag, # TODO: Implement padding / alignment
            "mode1v1" / Flag, # TODO: Implement padding / alignment
            "mode2v2" / Flag, # TODO: Implement padding / alignment
            "modeRace" / Flag, # TODO: Implement padding / alignment
            "modeTraining" / Flag, # TODO: Implement padding / alignment
            "unknown1" / HexBytes(1883),
        ),
        0x01: Struct( # PlayerSpawn
            "position" / Vector3,
            "angles" / Vector3,
            "teamA" / Flag, # TODO: Implement padding / alignment
            "teamB" / Flag, # TODO: Implement padding / alignment
            "initialSpawn" / Flag, # TODO: Implement padding / alignment
            "modeCTF" / Flag, # TODO: Implement padding / alignment
            "modeFFA" / Flag, # TODO: Implement padding / alignment
            "modeTDM" / Flag, # TODO: Implement padding / alignment
            "mode1v1" / Flag, # TODO: Implement padding / alignment
            "modeRace" / Flag, # TODO: Implement padding / alignment
            "mode2v2" / Bool8 # TODO: Implement padding / alignment # Horrible, awful hack
        ),
        0x03: Struct( # PointLight
            "position" / Vector3,
            "angles" / Vector3,
            "color" / ColorXRGB32l,
            "intensity" / Float32l,
            "nearAttenuation" / Float32l,
            "farAttenuation" / Float32l
        ),
        0x09: Struct( # Teleporter
            "position" / Vector3,
            "angles" / Vector3,
            "target" / PaddedString(32, ENC),
            "linkOutOnUsed" / PaddedString(32, ENC)
        ),
        0x0A: Struct( # Target
            "position" / Vector3,
            "angles" / Vector3,
            "name" / PaddedString(32, ENC),
            "nameNext" / PaddedString(32, ENC),
            "speed" / Float32l
        ),
        0x0B: Struct( # JumpPad
            "position" / Vector3,
            "angles" / Vector3,
            "target" / PaddedString(32, ENC)
        ),
        0x0C: Struct( # Effect
            "position" / Vector3,
            "angles" / Vector3,
            "effectName" / PaddedString(64, ENC),
            "effectScale" / Float32l,
            "material0Name" / PaddedString(256, ENC),
            "material0Albedo" / ColorARGB32l,
            "material1Name" / PaddedString(256, ENC),
            "material1Albedo" / ColorARGB32l,
            "material2Name" / PaddedString(256, ENC),
            "material2Albedo" / ColorARGB32l,
            "material3Name" / PaddedString(256, ENC),
            "material3Albedo" / ColorARGB32l,
            "material4Name" / PaddedString(256, ENC),
            "material4Albedo" / ColorARGB32l,
            "material5Name" / PaddedString(256, ENC),
            "material5Albedo" / ColorARGB32l,
            "material6Name" / PaddedString(256, ENC),
            "material6Albedo" / ColorARGB32l,
            "material7Name" / PaddedString(256, ENC),
            "material7Albedo" / ColorARGB32l,
            "pointLightOverridden" / Bool8, # Bool8
            "pointLightNear" / Float32l,
            "pointLightFar" / Float32l,
            "pointLightColor" / ColorXRGB32l,
            "pointLightIntensity" / Float32l,
            "pointLightTeamIndex" / Int8ul,
            "unknown1" / Array(31, Byte),
        ),
        0x0D: Struct( # Pickup
            "position" / Vector3,
            "angles" / Vector3,
            "unknown1" / Vector3,
            "pickupType" / Int8ul,
            "unknown2" / Array(9, Byte),
            "tokenIndex" / Int8ul,
            "unknown3" / Array(17, Byte),
            "linkOutOnPickedUp" / PaddedString(32, ENC)
        ),
        0x0F: Struct( # CameraPath
            "position" / Vector3,
            "angles" / Vector3,
            "entityIdAttachedTo" / Int32ul,
            "unknown1" / Int32ul,
            "unknown2" / Byte,
            "posLerp" / Int8ul,
            "angleLerp" / Int8ul,
            "unknown3" / Array(5, Byte)
        ),
        0x12: Struct( # RaceStart
            "position" / Vector3,
            "angles" / Vector3
        ),
        0x13: Struct( # RaceFinish
            "position" / Vector3,
            "angles" / Vector3
        ),
        0x14: Struct( # WeaponRestrictor
            "position" / Vector3,
            "angles" / Vector3,
            "allowedWeaponMask" / Int32ul # TODO: Convert this to flag?
        ),
        0x15: Struct( # Prefab
            "position" / Vector3,
            "angles" / Vector3,
            "prefabName" / PaddedString(64, ENC),
            "unknown" / Array(16, Byte)
        ),
        0x16: Struct( # VolumeSelect
            "position" / Vector3,
            "angles" / Vector3,
            "unknown1" / Array(4, Byte)
        ),
        0x17: Struct( # WorkshopScreenshot
            "position" / Vector3,
            "angles" / Vector3
        ),
        0x18: Struct( # ReflectionProbe
            "position" / Vector3,
            "angles" / Vector3
        ),
        0x19: Struct( # TriggerVolume
            "position" / Vector3,
            "angles" / Vector3,
            "unknown1" / Array(4, Byte),
            "linkOutOnEnter" / PaddedString(32, ENC),
            "linkOutOnExit" / PaddedString(32, ENC)
        ),
        0x1A: Struct(
            "position" / Vector3,
            "angles" / Vector3,
            "linkInDisplay" / PaddedString(32, ENC),
            "linkInShow" / PaddedString(32, ENC),
            "linkInHide" / PaddedString(32, ENC),
            "message" / PaddedString(256, ENC),
            "unknown" / HexBytes(4)
        ),
        0x1B: Struct( # Goal
            "position" / Vector3,
            "angles" / Vector3,
            "linkInDone" / PaddedString(32, ENC),
            "message" / PaddedString(256, ENC),
            "sortIndex" / Float32l,
        ),
        0x1C: Struct( # Turret
            "position" / Vector3,
            "angles" / Vector3,
            "weaponType" / Int8ul,
            "unknown1" / Array(23, Byte)
        ),
        0x1D: Struct( # Shootable
            "position" / Vector3,
            "angles" / Vector3,
            "linkOutDestroyed" / PaddedString(32, ENC),
            "target" / PaddedString(32, ENC),
            "unknown1" / Array(3, Byte), # This may be some form of padding for the next field, which is UInt8
            "weaponType" / Int8ul,
            "unknown2" / Int32sl,
            "unknown3" / Int32sl,
            "unknown4" / Int32sl,
            "unknown5" / Int32sl
        ),
        0x1E: Struct( # Accumulator
            "position" / Vector3,
            "angles" / Vector3,
            "linkInCount" / PaddedString(32, ENC),
            "linkOutDone" / PaddedString(32, ENC),
            "countTarget" / Int16ul,
            "unknown1" / Int16ul,
        ),
        0x1F: Struct( # Exit
            "position" / Vector3,
            "angles" / Vector3,
            "linkInExit" / PaddedString(32, ENC),
        ),
        0x20: Struct( # NavLink
            "position" / Vector3,
            "angles" / Vector3,
            "name" / PaddedString(32, ENC),
            "isStart" / Flag,
            "isBidirectional" / Flag,
            "unknown1" / Flag, # Padding?
            "unknown2" / Flag # Padding?
        )
    }),
    "brushes" / Array(this.numBrushes, PrefabBrush)
)


def registerPrefab(type, ctx):
    global PREFAB_LOOKUP

    PREFAB_LOOKUP[type.prefabName] = type.entities


Prefab = Struct(
    "prefabId" / Int32ul,
    "prefabName" / PaddedString(32, ENC),
    "numEntities" / Int32ul,
    "entities" / PrefabEntity[this.numEntities],
) * registerPrefab


def checkEntityDestroy(type, ctx):
    global ENTITY_LOOKUP

    if type.destroy:
        del ENTITY_LOOKUP[type.id]


def checkEntityCreate(type, ctx):
    global ENTITY_LOOKUP

    if ctx.m1.x1: # CREATE
        # print("REGISTER ENT", ctx.ent.id)
        ENTITY_LOOKUP[ctx.ent.id] = type


def lookupEntity(ctx):
    global ENTITY_LOOKUP

    return ENTITY_LOOKUP[ctx.ent.id]


def registerPrefabSubEntities(type, ctx):
    global PREFAB_LOOKUP

    # Check that prefab's m1 has 0x01 - CREATE
    if not ctx.m1.x1:
        return

    index = ctx.ent.id + 1

    for entity in PREFAB_LOOKUP[type.prefabName]:
        ENTITY_LOOKUP[index] = entity.entityType8
        index += 1


Entity = Struct(
    "ent" / ByteSwapped(BitStruct(
        "id" / BitsInteger(31),
        "destroy" / Bit,
    )) * checkEntityDestroy,
    "m1" / If(~this.ent.destroy, Mask8),
    "entityType" / If(~this.ent.destroy, IfThenElse(this.m1.x1, Int8ul * checkEntityCreate, Computed(lambda ctx: lookupEntity(ctx)))),
    "entityTypeS" / If(~this.ent.destroy, Computed(lambda ctx: ENTITY_TYPES[ctx.entityType])),
    "fields" / If(~this.ent.destroy, Switch(this.entityType, {
        0x00: Struct( # WorldSpawn
            # Here we fucking go...

            # e432273500010000000000000000000000000000000000000000000000000000000000000000

            "targetGameOverCamera" / If(this._.m1.x4, CString(ENC)),
            "sky.timeOfDay" / If(this._.m1.x8, Float32l),
            "sky.skyAngle" / If(this._.m1.x10, Float32l),
            "sky.skyTopColor" / If(this._.m1.x20, ColorXRGB32l),
            "sky.skyHorizonColor" / If(this._.m1.x40, ColorXRGB32l),
            "sky.skyBottomColor" / If(this._.m1.x80, ColorXRGB32l),

            "m2" / Mask8,

            "sky.skyTopColorIntensity" / If(this.m2.x1, Float32l),
            "sky.skyHorizonColorIntensity" / If(this.m2.x2, Float32l),
            "sky.skyBottomColorIntensity" / If(this.m2.x4, Float32l),
            "sky.sunColor" / If(this.m2.x8, ColorXRGB32l),
            "sky.sunIntensitySize" / If(this.m2.x10, Float32l),
            "sky.sunSharpness" / If(this.m2.x20, Float32l),
            "sky.sunEnabled" / If(this.m2.x40, Flag),
            "sky.horizonColor" / If(this.m2.x80, ColorXRGB32l),

            "m3" / Mask8,

            "sky.horizonIntensity" / If(this.m3.x1, Float32l),
            "sky.horizonHaloExponent" / If(this.m3.x2, Float32l),
            "sky.horizonHaloExponentSun" / If(this.m3.x4, Float32l),
            "sky.horizonHaloExponentSunIntensity" / If(this.m3.x8, Float32l),
            "sky.horizonLine" / If(this.m3.x10, Float32l),
            "sky.starsIntensity" / If(this.m3.x20, Float32l),
            "sky.cloudsColor" / If(this.m3.x40, Float32l),
            "sky.cloudsCoverage" / If(this.m3.x80, Float32l),

            "m4" / Mask8,

            "sky.cloudsSpeed.x" / If(this.m4.x1, Float32l),
            "sky.cloudsSpeed.y" / If(this.m4.x2, Float32l),
            "sky.cloudsCoverageMultiplier" / If(this.m4.x4, Float32l),
            "sky.cloudsBias" / If(this.m4.x8, Float32l),
            "sky.cloudsRoughness" / If(this.m4.x10, Float32l),
            "sky.cloudsDensity" / If(this.m4.x20, Float32l),
            "sky.cloudsThickness" / If(this.m4.x40, Float32l),
            "colorTeamA" / If(this.m4.x80, ColorXRGB32l),

            "m5" / Mask8,

            "colorTeamB" / If(this.m5.x1, ColorXRGB32l),
            "fogColor" / If(this.m5.x2, ColorXRGB32l),
            "fogDistanceStart" / If(this.m5.x4, Float32l),
            "fogDistanceEnd" / If(this.m5.x8, Float32l),
            "fogHeightTop" / If(this.m5.x10, Float32l),
            "fogHeightBottom" / If(this.m5.x20, Float32l),
            "title" / If(this.m5.x40, CString(ENC)),
            "ownerString" / If(this.m5.x80, CString(ENC)),

            "m6" / Mask8,

            "playersMin" / If(this.m6.x1, Int8ul),
            "playersMax" / If(this.m6.x2, Int8ul),
            "modeCTF" / If(this.m6.x4, Flag),
            "modeFFA" / If(this.m6.x8, Flag),
            "modeTDM" / If(this.m6.x10, Flag),
            "mode1v1" / If(this.m6.x20, Flag),
            "mode2v2" / If(this.m6.x40, Flag),
            "modeRace" / If(this.m6.x80, Flag),

            "m7" / Mask8,

            "modeTraining" / If(this.m7.x1, Flag),
            "m7x2" / If(this.m7.x2, HexBytes(2)), # e432273500010000000000000000000002ffff000000000000000000000000000000000000000000
            "m7x4" / If(this.m7.x4, HexBytes(1)), # e432273500010000000000000000000004ff000000000000000000000000000000000000000000
            "m7x8" / If(this.m7.x8, CString(ENC)), # e43227350001000000000000000000000867676767676700000000000000000000000000000000000000000000
            "m7x10" / If(this.m7.x10, HexBytes(1)), # e432273500010000000000000000000010ff000000000000000000000000000000000000000000
            "m7x20" / If(this.m7.x20, HexBytes(1)), # e432273500010000000000000000000020ff000000000000000000000000000000000000000000
            "m7x40" / If(this.m7.x40, HexBytes(1)), # e432273500010000000000000000000040ff000000000000000000000000000000000000000000
            "m7x80" / If(this.m7.x80, HexBytes(1)), # e432273500010000000000000000000080ff000000000000000000000000000000000000000000

            "m8" / Mask8,

            "m8x1" / If(this.m8.x1, HexBytes(1)), # e43227350001000000000000000000000001ff0000000000000000000000000000000000000000
            "m8x2" / If(this.m8.x2, CString(ENC)), # e43227350001000000000000000000000002676767676767000000000000000000000000000000000000000000
            "m8x4" / If(this.m8.x4, HexBytes(1)), # e43227350001000000000000000000000004ff0000000000000000000000000000000000000000
            "m8x8" / If(this.m8.x8, HexBytes(1)), # e43227350001000000000000000000000008ff0000000000000000000000000000000000000000
            "serverName" / If(this.m8.x10, CString(ENC)), # e432273500010000000000000000000000106767676767000000000000000000000000000000000000000000
            "mapName" / If(this.m8.x20, CString(ENC)), # e432273500010000000000000000000000206767676767000000000000000000000000000000000000000000
            "mutatorMask" / If(this.m8.x40, Int32ul), # e43227350001000000000000000000000040ffffffff0000000000000000000000000000000000000000 # TODO: Create mutatorMask primitive
            "m8x80" / If(this.m8.x80, HexBytes(8)), # e43227350001000000000000000000000080ffffffffffffffff0000000000000000000000000000000000000000

            "m9" / Mask8,

            "m9x1" / If(this.m9.x1, HexBytes(4)), # e4322735000100000000000000000000000001ffffffff00000000000000000000000000000000000000
            "m9x2" / If(this.m9.x2, HexBytes(4)), # e4322735000100000000000000000000000002ffffffff00000000000000000000000000000000000000
            "m9x4" / If(this.m9.x4, HexBytes(4)), # e4322735000100000000000000000000000004ffffffff00000000000000000000000000000000000000
            "m9x8" / If(this.m9.x8, HexBytes(4)), # e4322735000100000000000000000000000008ffffffff00000000000000000000000000000000000000
            "m9x10" / If(this.m9.x10, HexBytes(1)), # e4322735000100000000000000000000000010ff00000000000000000000000000000000000000
            "m9x20" / If(this.m9.x20, HexBytes(1)), # e4322735000100000000000000000000000020ff00000000000000000000000000000000000000 # Extremely bizarre behavior
            "m9x40" / If(this.m9.x40, HexBytes(1)), # e4322735000100000000000000000000000040ff00000000000000000000000000000000000000
            "m9x80" / If(this.m9.x80, HexBytes(1)), # e4322735000100000000000000000000000080ff00000000000000000000000000000000000000

            "m10" / Mask8,

            "m10x1" / If(this.m10.x1, HexBytes(2)), # e432273500010000000000000000000000000001ffff000000000000000000000000000000000000
            "m10x2" / If(this.m10.x2, HexBytes(2)), # e432273500010000000000000000000000000002ffff000000000000000000000000000000000000
            "m10x4" / If(this.m10.x4, HexBytes(1)), # e432273500010000000000000000000000000004ff000000000000000000000000000000000000
            "m10x8" / If(this.m10.x8, HexBytes(1)), # e432273500010000000000000000000000000008ff000000000000000000000000000000000000
            "m10x10" / If(this.m10.x10, HexBytes(1)), # e432273500010000000000000000000000000010ff000000000000000000000000000000000000
            "m10x20" / If(this.m10.x20, HexBytes(1)), # e432273500010000000000000000000000000020ff000000000000000000000000000000000000 # Extremely bizarre behavior
            "m10x40" / If(this.m10.x40, CString(ENC)), # e43227350001000000000000000000000000004067676767676700000000000000000000000000000000000000
            "m10x80" / If(this.m10.x80, HexBytes(4)), # e432273500010000000000000000000000000080ffffffff000000000000000000000000000000000000

            "m11" / Mask8,

            "m11x1" / If(this.m11.x1, HexBytes(4)), # e43227350001000000000000000000000000000001ffffffff0000000000000000000000000000000000
            "m11x2" / If(this.m11.x2, HexBytes(4)), # e43227350001000000000000000000000000000002ffffffff0000000000000000000000000000000000
            "m11x4" / If(this.m11.x4, HexBytes(4)), # e43227350001000000000000000000000000000004ffffffff0000000000000000000000000000000000
            "m11x8" / If(this.m11.x8, HexBytes(4)), # e43227350001000000000000000000000000000008ffffffff0000000000000000000000000000000000
            "m11x10" / If(this.m11.x10, HexBytes(2)), # e43227350001000000000000000000000000000010ffff0000000000000000000000000000000000
            "m11x20" / If(this.m11.x20, HexBytes(4)), # e43227350001000000000000000000000000000020ffffffff0000000000000000000000000000000000
            "m11x40" / If(this.m11.x40, HexBytes(4)), # e43227350001000000000000000000000000000040ffffffff0000000000000000000000000000000000
            "m11x80" / If(this.m11.x80, HexBytes(4)), # e43227350001000000000000000000000000000080ffffffff0000000000000000000000000000000000

            "m12" / Mask8,

            "m12x1" / If(this.m12.x1, HexBytes(4)), # e4322735000100000000000000000000000000000001ffffffff00000000000000000000000000000000
            "m12x2" / If(this.m12.x2, HexBytes(4)), # e4322735000100000000000000000000000000000002ffffffff00000000000000000000000000000000
            "m12x4" / If(this.m12.x4, HexBytes(4)), # e4322735000100000000000000000000000000000004ffffffff00000000000000000000000000000000
            "m12x8" / If(this.m12.x8, HexBytes(4)), # e4322735000100000000000000000000000000000008ffffffff00000000000000000000000000000000
            "m12x10" / If(this.m12.x10, HexBytes(4)), # e4322735000100000000000000000000000000000010ffffffff00000000000000000000000000000000
            "m12x20" / If(this.m12.x20, HexBytes(4)), # e4322735000100000000000000000000000000000020ffffffff00000000000000000000000000000000
            "m12x40" / If(this.m12.x40, HexBytes(4)), # e4322735000100000000000000000000000000000040ffffffff00000000000000000000000000000000
            "m12x80" / If(this.m12.x80, HexBytes(4)), # e4322735000100000000000000000000000000000080ffffffff00000000000000000000000000000000

            "m13" / Mask8,

            "m13x1" / If(this.m13.x1, HexBytes(4)), # e432273500010000000000000000000000000000000001ffffffff000000000000000000000000000000
            "m13x2" / If(this.m13.x2, HexBytes(4)), # e432273500010000000000000000000000000000000002ffffffff000000000000000000000000000000
            "m13x4" / If(this.m13.x4, HexBytes(4)), # e432273500010000000000000000000000000000000004ffffffff000000000000000000000000000000
            "m13x8" / If(this.m13.x8, HexBytes(4)), # e432273500010000000000000000000000000000000008ffffffff000000000000000000000000000000
            "m13x10" / If(this.m13.x10, HexBytes(4)), # e432273500010000000000000000000000000000000010ffffffff000000000000000000000000000000
            "m13x20" / If(this.m13.x20, HexBytes(4)), # e432273500010000000000000000000000000000000020ffffffff000000000000000000000000000000
            "m13x40" / If(this.m13.x40, HexBytes(4)), # e432273500010000000000000000000000000000000040ffffffff000000000000000000000000000000
            "m13x80" / If(this.m13.x80, HexBytes(4)), # e432273500010000000000000000000000000000000040ffffffff000000000000000000000000000000

            "m14" / Mask8,

            "m14x1" / If(this.m14.x1, HexBytes(4)), # e43227350001000000000000000000000000000000000001ffffffff0000000000000000000000000000
            "m14x2" / If(this.m14.x2, HexBytes(4)), # e43227350001000000000000000000000000000000000002ffffffff0000000000000000000000000000
            "m14x4" / If(this.m14.x4, HexBytes(4)), # e43227350001000000000000000000000000000000000004ffffffff0000000000000000000000000000
            "m14x8" / If(this.m14.x8, HexBytes(4)), # e43227350001000000000000000000000000000000000008ffffffff0000000000000000000000000000
            "m14x10" / If(this.m14.x10, HexBytes(4)), # e43227350001000000000000000000000000000000000010ffffffff0000000000000000000000000000
            "m14x20" / If(this.m14.x20, HexBytes(4)), # e43227350001000000000000000000000000000000000020ffffffff0000000000000000000000000000
            "m14x40" / If(this.m14.x40, HexBytes(4)), # e43227350001000000000000000000000000000000000040ffffffff0000000000000000000000000000
            "m14x80" / If(this.m14.x80, HexBytes(4)), # e43227350001000000000000000000000000000000000080ffffffff0000000000000000000000000000

            "m15" / Mask8,

            "m15x1" / If(this.m15.x1, HexBytes(4)), # e4322735000100000000000000000000000000000000000001ffffffff00000000000000000000000000
            "m15x2" / If(this.m15.x2, HexBytes(4)), # e4322735000100000000000000000000000000000000000002ffffffff00000000000000000000000000
            "m15x4" / If(this.m15.x4, HexBytes(4)), # e4322735000100000000000000000000000000000000000004ffffffff00000000000000000000000000
            "m15x8" / If(this.m15.x8, HexBytes(4)), # e4322735000100000000000000000000000000000000000008ffffffff00000000000000000000000000
            "m15x10" / If(this.m15.x10, HexBytes(4)), # e4322735000100000000000000000000000000000000000010ffffffff00000000000000000000000000
            "m15x20" / If(this.m15.x20, HexBytes(4)), # e4322735000100000000000000000000000000000000000020ffffffff00000000000000000000000000
            "m15x40" / If(this.m15.x40, HexBytes(4)), # e4322735000100000000000000000000000000000000000040ffffffff00000000000000000000000000
            "m15x80" / If(this.m15.x80, HexBytes(4)), # e4322735000100000000000000000000000000000000000080ffffffff00000000000000000000000000

            "m16" / Mask8,

            "m16x1" / If(this.m16.x1, HexBytes(4)), # e432273500010000000000000000000000000000000000000001ffffffff000000000000000000000000
            "m16x2" / If(this.m16.x2, HexBytes(4)), # e432273500010000000000000000000000000000000000000002ffffffff000000000000000000000000
            "m16x4" / If(this.m16.x4, HexBytes(4)), # e432273500010000000000000000000000000000000000000004ffffffff000000000000000000000000
            "m16x8" / If(this.m16.x8, HexBytes(4)), # e432273500010000000000000000000000000000000000000008ffffffff000000000000000000000000
            "m16x10" / If(this.m16.x10, HexBytes(4)), # e432273500010000000000000000000000000000000000000010ffffffff000000000000000000000000
            "m16x20" / If(this.m16.x20, HexBytes(4)), # e432273500010000000000000000000000000000000000000020ffffffff000000000000000000000000
            "m16x40" / If(this.m16.x40, HexBytes(4)), # e432273500010000000000000000000000000000000000000040ffffffff000000000000000000000000
            "m16x80" / If(this.m16.x80, HexBytes(4)), # e432273500010000000000000000000000000000000000000080ffffffff000000000000000000000000

            "m17" / Mask8,

            "m17x1" / If(this.m17.x1, HexBytes(4)), # e43227350001000000000000000000000000000000000000000001ffffffff0000000000000000000000
            "m17x2" / If(this.m17.x2, HexBytes(4)), # e43227350001000000000000000000000000000000000000000002ffffffff0000000000000000000000
            "m17x4" / If(this.m17.x4, HexBytes(4)), # e43227350001000000000000000000000000000000000000000004ffffffff0000000000000000000000
            "m17x8" / If(this.m17.x8, HexBytes(4)), # e43227350001000000000000000000000000000000000000000008ffffffff0000000000000000000000
            "m17x10" / If(this.m17.x10, HexBytes(4)), # e43227350001000000000000000000000000000000000000000010ffffffff0000000000000000000000
            "m17x20" / If(this.m17.x20, HexBytes(4)), # e43227350001000000000000000000000000000000000000000020ffffffff0000000000000000000000
            "m17x40" / If(this.m17.x40, HexBytes(4)), # e43227350001000000000000000000000000000000000000000040ffffffff0000000000000000000000
            "m17x80" / If(this.m17.x80, HexBytes(4)), # e43227350001000000000000000000000000000000000000000080ffffffff0000000000000000000000

            "m18" / Mask8,

            "m18x1" / If(this.m18.x1, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000001ffffffff00000000000000000000
            "m18x2" / If(this.m18.x2, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000002ffffffff00000000000000000000
            "m18x4" / If(this.m18.x4, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000004ffffffff00000000000000000000
            "m18x8" / If(this.m18.x8, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000008ffffffff00000000000000000000
            "m18x10" / If(this.m18.x10, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000010ffffffff00000000000000000000
            "m18x20" / If(this.m18.x20, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000020ffffffff00000000000000000000
            "m18x40" / If(this.m18.x40, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000040ffffffff00000000000000000000
            "m18x80" / If(this.m18.x80, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000080ffffffff00000000000000000000

            "m19" / Mask8,

            "m19x1" / If(this.m19.x1, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000001ffffffff000000000000000000
            "m19x2" / If(this.m19.x2, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000002ffffffff000000000000000000
            "m19x4" / If(this.m19.x4, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000004ffffffff000000000000000000
            "m19x8" / If(this.m19.x8, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000008ffffffff000000000000000000
            "m19x10" / If(this.m19.x10, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000010ffffffff000000000000000000
            "m19x20" / If(this.m19.x20, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000020ffffffff000000000000000000
            "m19x40" / If(this.m19.x40, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000040ffffffff000000000000000000
            "m19x80" / If(this.m19.x80, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000080ffffffff000000000000000000

            "m20" / Mask8,

            "m20x1" / If(this.m20.x1, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000001ffffffff0000000000000000
            "m20x2" / If(this.m20.x2, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000002ffffffff0000000000000000
            "m20x4" / If(this.m20.x4, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000004ffffffff0000000000000000
            "m20x8" / If(this.m20.x8, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000008ffffffff0000000000000000
            "m20x10" / If(this.m20.x10, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000010ffffffff0000000000000000
            "m20x20" / If(this.m20.x20, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000020ffffffff0000000000000000
            "m20x40" / If(this.m20.x40, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000040ffffffff0000000000000000
            "m20x80" / If(this.m20.x80, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000080ffffffff0000000000000000

            "m21" / Mask8,

            "m21x1" / If(this.m21.x1, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000001ffffffff00000000000000
            "m21x2" / If(this.m21.x2, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000002ffffffff00000000000000
            "m21x4" / If(this.m21.x4, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000004ffffffff00000000000000
            "m21x8" / If(this.m21.x8, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000008ffffffff00000000000000
            "m21x10" / If(this.m21.x10, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000010ffffffff00000000000000
            "m21x20" / If(this.m21.x20, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000020ffffffff00000000000000
            "m21x40" / If(this.m21.x40, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000040ffffffff00000000000000
            "m21x80" / If(this.m21.x80, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000080ffffffff00000000000000

            "m22" / Mask8,

            "m22x1" / If(this.m22.x1, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000001ffffffff000000000000
            "m22x2" / If(this.m22.x2, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000002ffffffff000000000000
            "m22x4" / If(this.m22.x4, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000004ffffffff000000000000
            "m22x8" / If(this.m22.x8, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000008ffffffff000000000000
            "m22x10" / If(this.m22.x10, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000010ffffffff000000000000
            "m22x20" / If(this.m22.x20, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000020ffffffff000000000000
            "m22x40" / If(this.m22.x40, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000040ffffffff000000000000
            "m22x80" / If(this.m22.x80, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000080ffffffff000000000000

            "m23" / Mask8,

            "m23x1" / If(this.m23.x1, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000001ffffffff0000000000
            "m23x2" / If(this.m23.x2, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000002ffffffff0000000000
            "m23x4" / If(this.m23.x4, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000004ffffffff0000000000
            "m23x8" / If(this.m23.x8, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000008ffffffff0000000000
            "m23x10" / If(this.m23.x10, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000010ffffffff0000000000
            "m23x20" / If(this.m23.x20, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000020ffffffff0000000000
            "m23x40" / If(this.m23.x40, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000040ffffffff0000000000
            "m23x80" / If(this.m23.x80, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000080ffffffff0000000000

            "m24" / Mask8,

            "m24x1" / If(this.m24.x1, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000001ffffffff00000000
            "m24x2" / If(this.m24.x2, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000002ffffffff00000000
            "m24x4" / If(this.m24.x4, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000004ffffffff00000000
            "m24x8" / If(this.m24.x8, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000008ffffffff00000000
            "m24x10" / If(this.m24.x10, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000010ffffffff00000000
            "m24x20" / If(this.m24.x20, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000020ffffffff00000000
            "m24x40" / If(this.m24.x40, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000040ffffffff00000000
            "m24x80" / If(this.m24.x80, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000080ffffffff00000000

            "m25" / Mask8,

            "m25x1" / If(this.m25.x1, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000000000001ffffffff000000
            "m25x2" / If(this.m25.x2, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000000000002ffffffff000000
            "m25x4" / If(this.m25.x4, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000000000004ffffffff000000
            "m25x8" / If(this.m25.x8, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000000000008ffffffff000000
            "m25x10" / If(this.m25.x10, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000000000010ffffffff000000
            "m25x20" / If(this.m25.x20, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000000000020ffffffff000000
            "m25x40" / If(this.m25.x40, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000000000040ffffffff000000
            "m25x80" / If(this.m25.x80, HexBytes(4)), # e432273500010000000000000000000000000000000000000000000000000000000080ffffffff000000

            "m26" / Mask8,

            "m26x1" / If(this.m26.x1, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000000000001ffffffff0000
            "m26x2" / If(this.m26.x2, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000000000002ffffffff0000
            "m26x4" / If(this.m26.x4, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000000000004ffffffff0000
            "m26x8" / If(this.m26.x8, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000000000008ffffffff0000
            "m26x10" / If(this.m26.x10, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000000000010ffffffff0000
            "m26x20" / If(this.m26.x20, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000000000020ffffffff0000
            "m26x40" / If(this.m26.x40, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000000000040ffffffff0000
            "m26x80" / If(this.m26.x80, HexBytes(4)), # e43227350001000000000000000000000000000000000000000000000000000000000080ffffffff0000

            "m27" / Mask8,

            "m27x1" / If(this.m27.x1, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000000000001ffffffff00
            "m27x2" / If(this.m27.x2, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000000000002ffffffff00
            "m27x4" / If(this.m27.x4, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000000000004ffffffff00
            "m27x8" / If(this.m27.x8, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000000000008ffffffff00
            "m27x10" / If(this.m27.x10, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000000000010ffffffff00
            "m27x20" / If(this.m27.x20, HexBytes(4)), # e4322735000100000000000000000000000000000000000000000000000000000000000020ffffffff00
            # 0x40 and above do not consume any data
        ),
        0x01: Struct( # PlayerSpawn
            "m1x2" / If(this._.m1.x2, HexBytes(1)), # f232273500010e00000002ff0000 01
            "isSelected" / If(this._.m1.x4, HexBytes(2)), # f232273500010e00000004ffff0000 01
            "position" / If(this._.m1.x8, Vector3),
            "angles" / If(this._.m1.x10, Vector3),
            "teamA" / If(this._.m1.x20, Flag),
            "teamB" / If(this._.m1.x40, Flag),
            "initialSpawn" / If(this._.m1.x80, Flag),

            "m2" / Mask8,

            "modeCTF" / If(this.m2.x1, Flag),
            "modeFFA" / If(this.m2.x2, Flag),
            "modeTDM" / If(this.m2.x4, Flag),
            "mode1v1" / If(this.m2.x8, Flag),
            "modeRace" / If(this.m2.x10, Flag),
            "mode2v2" / If(this.m2.x20, Flag),
            # 0x40 and above don't consume any data # f232273500010e000000004000 01
        ),
        0x02: Struct( # Player
            "primaryColor" / If(this._.m1.x2, Int8ul),
            "secondaryColor" / If(this._.m1.x4, Int8ul),
            "name" / If(this._.m1.x8, CString(ENC)),
            "m1x10" / If(this._.m1.x10, HexBytes(1)), # f232273500010a00000010ff01ee3227350000000000000000000000000000000000000000
            "m1x20" / If(this._.m1.x20, HexBytes(1)), # D2 33 27 35 00 01 0A 00 00 00 20 67 01 BA 33 27 35 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
            "m1x40" / If(this._.m1.x40, HexBytes(1)), # f232273500010a00000040ff01ee3227350000000000000000000000000000000000000000
            "m1x80" / If(this._.m1.x80, HexBytes(1)), # f232273500010a00000080ff01ee3227350000000000000000000000000000000000000000

            "m2" / Mask8,

            "timecode" / If(this.m2.x1, Int32ul),
            "position" / If(this.m2.x2, Vector3),
            "velocity" / If(this.m2.x4, Vector3),
            "m2x8" / If(this.m2.x8, HexBytes(2)), # f232273500010a0000000009f0322735ffff0000000000000000000000000000000000000000
            "viewAngle" / If(this.m2.x10, ViewAngle32l),
            "m2x20" / If(this.m2.x20, HexBytes(4)), # e432273500010a0000000020ffffffff0000000000000000000000000000000000000000
            "m2x40" / If(this.m2.x40, HexBytes(2)), # e432273500010a0000000040ffff0000000000000000000000000000000000000000
            "input" / If(this.m2.x80, InputMask),

            "m3" / Mask8,

            "timeSinceLastJump?" / If(this.m3.x1, Int16ul), # e432273500010a000000000001ffff00000000000000000000000000000000000000
            "m3x2" / If(this.m3.x2, HexBytes(2)), # e432273500010a000000000002ffff00000000000000000000000000000000000000
            "m3x4" / If(this.m3.x4, HexBytes(1)), # f232273500010a0000000001ee322735040000000000000000000000000000000000000000
            "m3x8" / If(this.m3.x8, HexBytes(1)), # f232273500010a0000000001ee322735080000000000000000000000000000000000000000
            "m3x10" / If(this.m3.x10, HexBytes(1)), # f232273500010a0000000001ee322735100000000000000000000000000000000000000000
            "m3x20" / If(this.m3.x20, HexBytes(1)), # f232273500010a0000000001ee322735100000000000000000000000000000000000000000
            "weaponHeld" / If(this.m3.x40, Int8ul), # f232273500010a0000000001ee322735200000000000000000000000000000000000000000 # See switching_weapons
            "m3x80" / If(this.m3.x80, HexBytes(1)), # f232273500010a0000000001ee322735800000000000000000000000000000000000000000

            "m4" / Mask8,

            "m4x1" / If(this.m4.x1, HexBytes(4)), # f232273500010a0000000001ee322735000100000000000000000000000000000000000000000000
            "glowColor" / If(this.m4.x2, HexBytes(1)), # f232273500010a0000000001ee322735000200000000000000000000000000000000000000
            "m4x4" / If(this.m4.x4, HexBytes(1)), # f232273500010a0000000001ee322735000400000000000000000000000000000000000000
            "m4x8" / If(this.m4.x8, HexBytes(1)), # f232273500010a0000000001ee322735000800000000000000000000000000000000000000
            "m4x10" / If(this.m4.x10, HexBytes(1)), # f232273500010a0000000001ee322735001000000000000000000000000000000000000000
            "m4x20" / If(this.m4.x20, HexBytes(1)), # f232273500010a0000000001ee322735002000000000000000000000000000000000000000
            "m4x40" / If(this.m4.x40, HexBytes(1)), # f232273500010a0000000001ee322735004000000000000000000000000000000000000000
            "m4x80" / If(this.m4.x80, HexBytes(1)), # f232273500010a0000000001ee322735008000000000000000000000000000000000000000

            "m5" / Mask8,

            "m5x1" / If(this.m5.x1, HexBytes(2)), # f232273500010a0000000001ee32273500000100000000000000000000000000000000000000
            "m5x2" / If(this.m5.x2, HexBytes(4)), # f232273500010a0000000001ee322735000002000000000000000000000000000000000000000000
            "m5x4" / If(this.m5.x4, HexBytes(4)), # f232273500010a0000000001ee322735000004000000000000000000000000000000000000000000
            "m5x8" / If(this.m5.x8, HexBytes(1)), # f232273500010a0000000001ee322735000008000000000000000000000000000000000000
            "cameraRotation" / If(this.m5.x10, Vector3), # f232273500010a0000000001ee322735000010ffffffffffffffffffffffff0000000000000000000000000000000000 # Probably a Vector3, rotates player's camera
            "m5x20" / If(this.m5.x20, HexBytes(1)), # f232273500010a0000000001ee322735000020000000000000000000000000000000000000
            "m5x40" / If(this.m5.x40, HexBytes(1)), # f232273500010a0000000001ee322735000040000000000000000000000000000000000000
            "m5x80" / If(this.m5.x80, HexBytes(1)), # f232273500010a0000000001ee322735000080000000000000000000000000000000000000

            "m6" / Mask8,

            "m6x1" / If(this.m6.x1, HexBytes(2)), # f232273500010a0000000001ee32273500000001010000000000000000000000000000000000
            "m6x2" / If(this.m6.x2, HexBytes(2)), # f232273500010a0000000001ee3227350000000200ff00000000000000000000000000000000 # If > 0, player has Quad. Maybe something like quadTicksRemaining?
            "m6x4" / If(this.m6.x4, HexBytes(2)), # f232273500010a0000000001ee32273500000004ffff00000000000000000000000000000000 # If > 0, player has Shield. Maybe something like quadTicksRemaining?
            "m6x8" / If(this.m6.x8, HexBytes(2)), # f232273500010a0000000001ee32273500000008000000000000000000000000000000000000 # If = 0, player dies. If = 1, player lives. Probably health. Probably signed.
            "m6x10" / If(this.m6.x10, HexBytes(1)), # f232273500010a0000000001ee32273500000010ff00000000000000000000000000000000
            "m6x20" / If(this.m6.x20, HexBytes(1)), # f232273500010a0000000001ee322735000000206700000000000000000000000000000000
            "m6x40" / If(this.m6.x40, HexBytes(2)), # f232273500010a0000000001ee32273500000040000000000000000000000000000000000000
            "m6x80" / If(this.m6.x80, HexBytes(4)), # f232273500010a0000000001ee322735000000800000000000000000000000000000000000000000

            "m7" / Mask8,

            "m7x1" / If(this.m7.x1, HexBytes(1)), # f232273500010a0000000001ee3227350000000001ff000000000000000000000000000000
            "m7x2" / If(this.m7.x2, HexBytes(1)), # f232273500010a0000000001ee3227350000000002ff000000000000000000000000000000
            "m7x4" / If(this.m7.x4, HexBytes(1)), # f232273500010a0000000001ee3227350000000004ff000000000000000000000000000000
            "m7x8" / If(this.m7.x8, HexBytes(1)), # f232273500010a0000000001ee3227350000000008ff000000000000000000000000000000
            "m7x10" / If(this.m7.x10, HexBytes(1)), # f232273500010a0000000001ee3227350000000010ff000000000000000000000000000000
            "m7x20" / If(this.m7.x20, HexBytes(1)), # f232273500010a0000000001ee3227350000000020ff000000000000000000000000000000
            "m7x40" / If(this.m7.x40, HexBytes(2)), # f232273500010a0000000001ee3227350000000040ffff000000000000000000000000000000
            "m7x80" / If(this.m7.x80, HexBytes(2)), # f232273500010a0000000001ee3227350000000080ffff000000000000000000000000000000

            "m8" / Mask8,

            "m8x1" / If(this.m8.x1, HexBytes(1)), # f232273500010a0000000001ee322735000000000001ff0000000000000000000000000000
            "m8x2" / If(this.m8.x2, HexBytes(1)), # f232273500010a0000000001ee322735000000000002ff0000000000000000000000000000
            "m8x4" / If(this.m8.x4, HexBytes(4)), # f232273500010a0000000001ee322735000000000004ffffffff0000000000000000000000000000
            "m8x8" / If(this.m8.x8, HexBytes(4)), # f232273500010a0000000001ee322735000000000008ffffffff0000000000000000000000000000
            "m8x10" / If(this.m8.x10, HexBytes(4)), # f232273500010a0000000001ee322735000000000010ffffffff0000000000000000000000000000
            "horSpeed?" / If(this.m8.x20, Int16ul), # f232273500010a0000000001ee322735000000000020ffff0000000000000000000000000000
            "m8x40" / If(this.m8.x40, HexBytes(4)), # f232273500010a0000000001ee322735000000000040ffffffff0000000000000000000000000000
            "meleeSkin" / If(this.m8.x80, Int32ul), # f232273500010a0000000001ee322735000000000080ffffffff0000000000000000000000000000

            "m9" / Mask8,

            "headSkin" / If(this.m9.x1, Int32ul),
            "legsSkin" / If(this.m9.x2, Int32ul),
            "armsSkin" / If(this.m9.x4, Int32ul),
            "chestSkin" / If(this.m9.x8, Int32ul),
            "burstgunSkin" / If(this.m9.x10, Int32ul),
            "shotgunSkin" / If(this.m9.x20, Int32ul), # TODO: Verify
            "grenadeLauncherSkin" / If(this.m9.x40, Int32ul), # TODO: Verify
            "plasmaGunSkin" / If(this.m9.x80, Int32ul), # TODO: Verify

            "m10" / Mask8,

            "rocketLauncherSkin" / If(this.m10.x1, Int32ul), # TODO: Verify
            "ionCannonSkin" / If(this.m10.x2, Int32ul), # TODO: Verify
            "boltRifleSkin" / If(this.m10.x4, Int32ul), # TODO: Verify
            "m10x8" / If(this.m10.x8, HexBytes(8)), # f232273500010a0000000001ee32273500000000000000080000000000000000000000000000000000000000 # steamId?
            "country" / If(this.m10.x10, CString(ENC)), # DE 82 4D 36 00 01 0A 00 00 00 00 01 CB 82 4D 36 00 00 00 00 00 00 00 10 61 62 63 64 64 00 00 00 00 00 00 00 00 00 00 00 00 00
            "m10x20" / If(this.m10.x20, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000020ffff000000000000000000000000
            "m10x40" / If(this.m10.x40, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000040ffff000000000000000000000000
            "m10x80" / If(this.m10.x80, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000080ffff000000000000000000000000

            "m11" / Mask8,

            "m11x1" / If(this.m11.x1, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000001ff0000000000000000000000
            "m11x2" / If(this.m11.x2, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000002ff0000000000000000000000
            "m11x4" / If(this.m11.x4, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000004ff0000000000000000000000
            "m11x8" / If(this.m11.x8, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000008ff0000000000000000000000
            "m11x10" / If(this.m11.x10, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000010ff0000000000000000000000
            "m11x20" / If(this.m11.x20, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000020ff0000000000000000000000
            "m11x40" / If(this.m11.x40, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000040ff0000000000000000000000
            "m11x80" / If(this.m11.x80, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000080ff0000000000000000000000

            "m12" / Mask8,

            "m12x1" / If(this.m12.x1, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000001ffff00000000000000000000
            "m12x2" / If(this.m12.x2, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000002ffff00000000000000000000
            "m12x4" / If(this.m12.x4, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000004ffff00000000000000000000
            "m12x8" / If(this.m12.x8, HexBytes(2)), # f232273500010a0000000001f032273500000000000000000008ffff00000000000000000000
            "distanceTravelled" / If(this.m12.x10, Float32l),              # f232273500010a0000000001f032273500000000000000000010ffffffff00000000000000000000
            "m12x20" / If(this.m12.x20, HexBytes(1)),         # f232273500010a0000000001ee32273500000000000000000020ff00000000000000000000
            "m12x40" / If(this.m12.x40, HexBytes(1)),         # f232273500010a0000000001ee32273500000000000000000040ff00000000000000000000
            "m12x80" / If(this.m12.x80, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000080ffff00000000000000000000

            "m13" / Mask8,

            "m13x1" / If(this.m13.x1, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000001ffff000000000000000000
            "m13x2" / If(this.m13.x2, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000002ffff000000000000000000
            "m13x4" / If(this.m13.x4, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000004ffff000000000000000000
            "m13x8" / If(this.m13.x8, HexBytes(1)), # f232273500010a0000000001ee3227350000000000000000000008ff000000000000000000
            "m13x10" / If(this.m13.x10, HexBytes(1)), # f232273500010a0000000001ee3227350000000000000000000010ff000000000000000000
            "m13x20" / If(this.m13.x20, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000020ffff000000000000000000
            "m13x40" / If(this.m13.x40, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000040ffff000000000000000000
            "m13x80" / If(this.m13.x80, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000080ffff000000000000000000

            "m14" / Mask8,

            "m14x1" / If(this.m14.x1, HexBytes(2)), # f232273500010a0000000001ee322735000000000000000000000001ffff0000000000000000
            "m14x2" / If(this.m14.x2, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000000000002ff0000000000000000
            "m14x4" / If(this.m14.x4, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000000000004ff0000000000000000
            "m14x8" / If(this.m14.x8, HexBytes(2)), # f232273500010a0000000001ee322735000000000000000000000008ffff0000000000000000
            "m14x10" / If(this.m14.x10, HexBytes(2)), # f232273500010a0000000001ee322735000000000000000000000010ffff0000000000000000
            "m14x20" / If(this.m14.x20, HexBytes(2)), # f232273500010a0000000001ee322735000000000000000000000020ffff0000000000000000
            "m14x40" / If(this.m14.x40, HexBytes(2)), # f232273500010a0000000001ee322735000000000000000000000040ffff0000000000000000
            "m14x80" / If(this.m14.x80, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000000000080ff0000000000000000

            "m15" / Mask8,

            "m15x1" / If(this.m15.x1, HexBytes(1)), # f232273500010a0000000001ee32273500000000000000000000000001ff00000000000000
            "m15x2" / If(this.m15.x2, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000000000002ffff00000000000000
            "m15x4" / If(this.m15.x4, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000000000004ffff00000000000000
            "m15x8" / If(this.m15.x8, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000000000008ffff00000000000000
            "m15x10" / If(this.m15.x10, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000000000010ffff00000000000000
            "m15x20" / If(this.m15.x20, HexBytes(1)), # f232273500010a0000000001ee32273500000000000000000000000020ff00000000000000
            "m15x40" / If(this.m15.x40, HexBytes(1)), # f232273500010a0000000001ee32273500000000000000000000000040ff00000000000000
            "m15x80" / If(this.m15.x80, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000000000080ffff00000000000000

            "m16" / Mask8,

            "m16x1" / If(this.m16.x1, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000000000001ffff000000000000
            "m16x2" / If(this.m16.x2, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000000000002ffff000000000000
            "m16x4" / If(this.m16.x4, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000000000004ffff000000000000
            "m16x8" / If(this.m16.x8, HexBytes(1)), # f232273500010a0000000001ee3227350000000000000000000000000008ff000000000000
            "m16x10" / If(this.m16.x10, HexBytes(1)), # f232273500010a0000000001ee3227350000000000000000000000000010ff000000000000
            "m16x20" / If(this.m16.x20, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000000000020ffff000000000000
            "m16x40" / If(this.m16.x40, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000000000040ffff000000000000
            "m16x80" / If(this.m16.x80, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000000000080ffff000000000000 # HitMarker on the first tick this happens?

            "m17" / Mask8,

            "m17x1" / If(this.m17.x1, HexBytes(2)), # f232273500010a0000000001ee322735000000000000000000000000000001ffff0000000000
            "m17x2" / If(this.m17.x2, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000000000000000002ff0000000000
            "m17x4" / If(this.m17.x4, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000000000000000004ff0000000000
            "m17x8" / If(this.m17.x8, HexBytes(2)), # f232273500010a0000000001ee322735000000000000000000000000000008ffff0000000000
            "m17x10" / If(this.m17.x10, HexBytes(2)), # f232273500010a0000000001ee322735000000000000000000000000000010ffff0000000000
            "m17x20" / If(this.m17.x20, HexBytes(2)), # f232273500010a0000000001ee322735000000000000000000000000000020ffff0000000000 # HitMarker on the first tick this happens?
            "m17x40" / If(this.m17.x40, HexBytes(2)), # f232273500010a0000000001ee322735000000000000000000000000000040ffff0000000000
            "m17x80" / If(this.m17.x80, HexBytes(1)), # f232273500010a0000000001ee322735000000000000000000000000000080ff0000000000

            "m18" / Mask8,

            "m18x1" / If(this.m18.x1, HexBytes(1)), # f232273500010a0000000001ee32273500000000000000000000000000000001ff00000000
            "m18x2" / If(this.m18.x2, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000000000000000002ffff00000000
            "m18x4" / If(this.m18.x4, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000000000000000004ffff00000000
            "m18x8" / If(this.m18.x8, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000000000000000008ffff00000000 # HitMarker on the first tick this happens?
            "m18x10" / If(this.m18.x10, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000000000000000010ffff00000000
            "m18x20" / If(this.m18.x20, HexBytes(1)), # f232273500010a0000000001ee32273500000000000000000000000000000020ff00000000
            "m18x40" / If(this.m18.x40, HexBytes(1)), # f232273500010a0000000001ee32273500000000000000000000000000000040ff00000000
            "m18x80" / If(this.m18.x80, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000000000000000080ffff00000000

            "m19" / Mask8,

            "m19x1" / If(this.m19.x1, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000000000000000001ffff000000
            "m19x2" / If(this.m19.x2, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000000000000000002ffff000000
            "m19x4" / If(this.m19.x4, HexBytes(2)), # f232273500010a0000000001ee3227350000000000000000000000000000000004ffff000000
            "recDistanceTravelled?" / If(this.m19.x8, Float32l), # f232273500010a0000000001ee3227350000000000000000000000000000000008ffffffff000000
            "recTime?" / If(this.m19.x10, Int32ul), # f232273500010a0000000001ee3227350000000000000000000000000000000010ffffffff000000
            "recTopSpeed?" / If(this.m19.x20, Int16ul), # f232273500010a0000000001ee3227350000000000000000000000000000000020ffff000000
            "m19x40" / If(this.m19.x40, HexBytes(4)), # f232273500010a0000000001ee3227350000000000000000000000000000000040ffffffff000000
            "m19x80" / If(this.m19.x80, HexBytes(4)), # f232273500010a0000000001ee3227350000000000000000000000000000000080ffffffff000000

            "m20" / Mask8,

            "m20x1" / If(this.m20.x1, HexBytes(2)), # f232273500010a0000000001ee322735000000000000000000000000000000000001ffff0000
            "m20x2" / If(this.m20.x2, HexBytes(4)), # f232273500010a0000000001ee322735000000000000000000000000000000000002ffffffff0000
            "m20x4" / If(this.m20.x4, HexBytes(4)), # f232273500010a0000000001ee322735000000000000000000000000000000000004ffffffff0000
            "m20x8" / If(this.m20.x8, HexBytes(2)), # f232273500010a0000000001ee322735000000000000000000000000000000000008ffff0000
            "m20x10" / If(this.m20.x10, HexBytes(4)), # f232273500010a0000000001ee322735000000000000000000000000000000000010ffffffff0000
            "m20x20" / If(this.m20.x20, HexBytes(4)), # f232273500010a0000000001ee322735000000000000000000000000000000000020ffffffff0000
            "m20x40" / If(this.m20.x40, HexBytes(2)), # f232273500010a0000000001ee322735000000000000000000000000000000000040ffff0000
            "m20x80" / If(this.m20.x80, HexBytes(4)), # f232273500010a0000000001ee322735000000000000000000000000000000000080ffffffff0000

            "m21" / Mask8,

            "m21x1" / If(this.m21.x1, HexBytes(4)), # f232273500010a0000000001ee32273500000000000000000000000000000000000001ffffffff00
            "m21x2" / If(this.m21.x2, HexBytes(2)), # f232273500010a0000000001ee32273500000000000000000000000000000000000002ffff00

            # That's it, 0x4 and above does not consume any data.
        ),
        0x03: Struct( # PointLight
            "m1x2" / If(this._.m1.x2, HexBytes(1)), # f232273500010e00000002ff00 03
            "isSelected" / If(this._.m1.x4, Int16ul), # f232273500010e00000004ffff00 03
            "position" / If(this._.m1.x8, Vector3),
            "color" / If(this._.m1.x10, ColorXRGB32l),
            "intensity" / If(this._.m1.x20, Float32l),
            "nearAttenuation" / If(this._.m1.x40, Float32l),
            "farAttenuation" / If(this._.m1.x80, Float32l)
        ),
        0x04: Struct( # Projectile (Grenade)
            "m1x2" / If(this._.m1.x2, HexBytes(1)), # Something to do with when the projectile stops travelling and freezes in place. In general 0x02 seems like an exit code of sorts?
            "origin" / If(this._.m1.x4, Vector3),
            "angle" / If(this._.m1.x8, Vector3),
            "spawnedAtTimecode" / If(this._.m1.x10, Int32ul),
            "spawnedByEntityId" / If(this._.m1.x20, Int32ul),
            "projectileDeathLocation" / If(this._.m1.x40, Vector3),
            # 0x80 does not consume any data # 0C 00 00 00 C2 A2 00 96 23 C2 18 B3 2C 42 00 E0 11 43

            # 0C 00 00 00
            # 3D
            # 04
            # 00 00 00 00 00 00 0A 42 00 00 00 00
            # 64 2B AC 43 00 60 DB 3F 00 00 00 00
            # 8B 4F 70 44
            # 05 00 00 00

            # 0C 00 00 00
            # 42
            # A2
            # 00 96 23 C2 18 B3 2C 42 00 E0 11 43
        ),
        0x05: Struct( # Projectile (Rocket)
            "m1x2" / If(this._.m1.x2, HexBytes(1)), # Something to do with when the projectile stops travelling and freezes in place. In general 0x02 seems like an exit code of sorts?
            "origin" / If(this._.m1.x4, Vector3),
            "angle" / If(this._.m1.x8, Vector3),
            "spawnedAtTimecode" / If(this._.m1.x10, Int32ul),
            "spawnedByEntityId" / If(this._.m1.x20, Int32ul),
            "projectileDeathLocation" / If(this._.m1.x40, Vector3),
            "m1x80" / If(this._.m1.x80, Vector3)

            # 0C 00 00 00 - entityId
            # 3D - fieldMask
            # 05 - entityType
            # 7B 32 12 C1 45 C4 07 42 A2 B0 D3 41 - origin
            # 90 79 AA 43 00 40 92 3F 00 00 00 00 - angle
            # E9 B1 8C 40 - spawnedAtTimecode
            # 05 00 00 00 - spawnedByEntityId

            # 0C 00 00 00 - entityId
            # C2 - fieldMask
            # A2 - unknown
            # 2D 86 4A C2 EE 3F FB 41 00 A0 12 43 - projectileDeathLocation?
            #
            # DB 0F 49 40 - unknown, 3.14159274????
            # 00 00 00 00 00 00 00 00
        ),
        0x06: Struct( # Projectile (Plasma)
            "m1x2" / If(this._.m1.x2, HexBytes(1)), # Something to do with when the projectile stops travelling and freezes in place. In general 0x02 seems like an exit code of sorts?
            "origin" / If(this._.m1.x4, Vector3),
            "angle" / If(this._.m1.x8, ViewAngle32l),
            "spawnedAtTimecode" / If(this._.m1.x10, Int32ul),
            "spawnedByEntityId" / If(this._.m1.x20, Int32ul),
            "projectileDeathLocation" / If(this._.m1.x40, Vector3),
            "m1x80" / If(this._.m1.x80, Int32sl) # Maybe signed?

            # 0C 00 00 00 - entityId
            # 35 - fieldMask (0x01 - CREATE)
            # 06 - entityType
            # 00 00 00 00 00 00 0A 42 00 00 E0 41 - projectileOrigin 0x04
            # FA CD 0E 3F - spawnedAtTimecode? 0x10
            # 05 00 00 00 - spawnedByEntityId? 0x20

            # 0C 00 00 00
            # C2 - fieldMask
            # A2 - unknown
            # D3 69 D1 42 00 00 AB C1 25 23 B0 42 - projectileDeathLocation?
            # 00 00 00 C0 - unknown, = -2 if signed

        ),
        0x07: Struct( # Projectile (Burstgun)
            "m1x2" / If(this._.m1.x2, HexBytes(1)), # Something to do with when the projectile stops travelling and freezes in place. In general 0x02 seems like an exit code of sorts?
            "origin" / If(this._.m1.x4, Vector3),
            "angle" / If(this._.m1.x8, ViewAngle32l),
            "spawnedAtTimecode" / If(this._.m1.x10, Int32ul),
            "spawnedByEntityId" / If(this._.m1.x20, Int32ul),
            "m1x40" / If(this._.m1.x40, Vector3),
            "m1x80" / If(this._.m1.x80, Int32sl) # Maybe signed?

            # 08 00 00 00 - entityId
            # 3D - fieldMask (0x01 - CREATE)
            # 07 - entityType
            # 1F E9 C6 42 93 AB 53 42 BB D1 D9 41 - projectileOrigin
            # 07 05 12 13 - projectileAngle
            # 92 63 2A 34 - spawnedAtTimecode
            # 03 00 00 00 - spawnedByEntityId

            # 08 00 00 00
            # C2 - fieldMask
            # A2 - unknown
            # F4 50 EC 42 00 00 BF C1 C5 F4 31 43 - projectileDeathLocation?
            # 00 00 00 C0 - unknown, = -2 if signed
        ),
        0x08: Struct( # Projectile (Stake)
            "m1x2" / If(this._.m1.x2, HexBytes(1)), # Something to do with when the projectile stops travelling and freezes in place. In general 0x02 seems like an exit code of sorts?
            "origin" / If(this._.m1.x4, Vector3),
            "angle" / If(this._.m1.x8, ViewAngle32l),
            "spawnedAtTimecode" / If(this._.m1.x10, Int32ul),
            "spawnedByEntityId" / If(this._.m1.x20, Int32ul),
            "projectileDeathLocation" / If(this._.m1.x40, Vector3),

            "m2" / Mask8,

            "projectileDeathAngle" / If(this.m2.x1, Vector3) # projectileStateAngle

            # 0x2 and above don't consume any data...
        ),
        0x09: Struct( # Teleporter
            "isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 09
            "target" / If(this._.m1.x4, CString(ENC)),
            "linkOutOnExit" / If(this._.m1.x8, CString(ENC))
            # 0x10 and above don't consume any data # f232273500010e0000001000 09
        ),
        0x0A: Struct( # Target
            "isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 0A
            "position" / If(this._.m1.x4, Vector3),
            "angles" / If(this._.m1.x8, Vector3),
            "name" / If(this._.m1.x10, CString(ENC)),
            "nameNext" / If(this._.m1.x20, CString(ENC)),
            "speed" / If(this._.m1.x40, Float32l)
            # 0x80 does not consume any data # f232273500010e0000008000 0A
        ),
        0x0B: Struct( # JumpPad
            "isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 0B
            "target" / If(this._.m1.x4, CString(ENC)),
            # 0x08 and above don't consume any data # f232273500010e0000000800 0B
        ),
        0x0C: Struct( # Effect
            "m1x2" / If(this._.m1.x2, HexBytes(1)), # f232273500010e00000002ff0000000000 0C
            "isSelected" / If(this._.m1.x4, Int16ul), # f232273500010e00000004ffff0000000000 0C
            "position" / If(this._.m1.x8, Vector3),
            "angles" / If(this._.m1.x10, Vector3),
            "effectName" / If(this._.m1.x20, CString(ENC)),
            "effectScale" / If(this._.m1.x40, Float32l),
            "material0Name" / If(this._.m1.x80, CString(ENC)),

            "m2" / Mask8,

            "material0Albedo" / If(this.m2.x1, ColorARGB32l),
            "material1Name" / If(this.m2.x2, CString(ENC)),
            "material1Albedo" / If(this.m2.x4, ColorARGB32l),
            "material2Name" / If(this.m2.x8, CString(ENC)),
            "material2Albedo" / If(this.m2.x10, ColorARGB32l),
            "material3Name" / If(this.m2.x20, CString(ENC)),
            "material3Albedo" / If(this.m2.x40, ColorARGB32l),
            "material4Name" / If(this.m2.x80, CString(ENC)),

            "m3" / Mask8,

            "material4Albedo" / If(this.m3.x1, ColorARGB32l),
            "material5Name" / If(this.m3.x2, CString(ENC)),
            "material5Albedo" / If(this.m3.x4, ColorARGB32l),
            "material6Name" / If(this.m3.x8, CString(ENC)),
            "material6Albedo" / If(this.m3.x10, ColorARGB32l),
            "material7Name" / If(this.m3.x20, CString(ENC)),
            "material7Albedo" / If(this.m3.x40, ColorARGB32l),

            "pointLightOverridden" / If(this.m3.x80, Flag), # Bool8

            "m4" / Mask8,

            "pointLightNear" / If(this.m4.x1, Float32l),
            "pointLightFar" / If(this.m4.x2, Float32l),
            "pointLightColor" / If(this.m4.x4, ColorXRGB32l),
            "pointLightIntensity" / If(this.m4.x8, Float32l),
            "pointLightTeamIndex" / If(this.m4.x10, Int8sl),

            "spotLightOverridden" / If(this.m4.x20, Flag), # Bool8
            "spotLightNear" / If(this.m4.x40, Float32l),
            "spotLightFar" / If(this.m4.x80, Float32l),

            "m5" / Mask8,

            "spotLightInnerAngleDegrees" / If(this.m5.x1, Float32l),
            "spotLightOuterAngleDegrees" / If(this.m5.x2, Float32l),
            "spotLightColor" / If(this.m5.x4, ColorXRGB32l),
            "spotLightIntensity" / If(this.m5.x8, Float32l),
            "spotLightCastsShadow" / If(this.m5.x10, Flag), # Bool8
            "spotLightTeamIndex" / If(this.m5.x20, Int8sl)
        ),
        0x0D: Struct( # Pickup
            "m1x2" / If(this._.m1.x2, HexBytes(1)), # f232273500010e00000002ff000000
            "isSelected" / If(this._.m1.x4, Int16ul), # f232273500010e00000004ffff000000
            "position" / If(this._.m1.x8, Vector3),
            "angles" / If(this._.m1.x10, Vector3),
            "m1x20" / If(this._.m1.x20, Vector3), # f232273500010e00000020ffffffffffffffffffffffff000000
            "linkOutOnPickup" / If(this._.m1.x40, CString(ENC)),
            "tokenIndex" / If(this._.m1.x80, Int8ul),

            "m2" / Mask8,

            "pickupType" / If(this.m2.x1, Int8ul),
            "m2x2" / If(this.m2.x2, HexBytes(1)), # f232273500010e0000000002ff0000
            "m2x4" / If(this.m2.x4, HexBytes(1)), # f232273500010e0000000004ff0000
            "m2x8" / If(this.m2.x8, HexBytes(1)), # f232273500010e0000000008ff0000
            "m2x10" / If(this.m2.x10, HexBytes(1)), # f232273500010e0000000010ff0000
            "m2x20" / If(this.m2.x20, HexBytes(1)), # f232273500010e0000000020ff0000
            "m2x40" / If(this.m2.x40, HexBytes(1)), # f232273500010e0000000040ff0000
            "m2x80" / If(this.m2.x80, HexBytes(1)), # f232273500010e0000000080ff0000

            "m3" / Mask8,

            "m3x1" / If(this.m3.x1, HexBytes(1)), # f232273500010e000000000001ff00
            "m3x2" / If(this.m3.x2, HexBytes(1)), # f232273500010e000000000002ff00
            "m3x4" / If(this.m3.x4, HexBytes(4)), # f232273500010e000000000004ffffffff00
            "m3x8" / If(this.m3.x8, HexBytes(4)), # f232273500010e000000000008ffffffff00
            "m3x10" / If(this.m3.x10, HexBytes(4)), # f232273500010e000000000010ffffffff00
            "m3x20" / If(this.m3.x20, HexBytes(4)), # f232273500010e000000000020ffffffff00
            # 0x40 and above do not consume any data # f232273500010e00000000004000
        ),
        0x0E: Struct( # ChatMessage ?
            "m1x2" / If(this._.m1.x2, HexBytes(1)),
            "m1x4" / If(this._.m1.x4, Vector3), # e432273500010c000000570ea70000000000000000050000006a696d6d790000 # What the fuck was I on while writing this?
            "m1x8" / If(this._.m1.x8, Vector3), # e432273500010c0000005b0ea70000000000000000050000006a696d6d790000 # What the fuck was I on while writing this?
            "senderId" / If(this._.m1.x10, Int32ul),
            "m1x20" / If(this._.m1.x20, HexBytes(4)), # e432273500010c000000730ea705000000020000006a696d6d790000 # Seems to affect who receives the message. Might be an enum for global, team, spec, or a receiverId
            "content" / If(this._.m1.x40, CString(ENC))
            # 0x80 does not consume additional data # e432273500010c000000f30ea005000000010000006a696d6d790000

            # 0C 00 00 00 - entityId
            # 53 - fieldMask (importantly, 0x01 - CREATE is present)
            # 0E - entityType
            # A7 - unknown (0x02? It would make sense that ChatMessage entities have no need for 0x02 - DESTROY...)
            # 05 00 00 00 - senderIdDivBy2? (0x10?)
            # 6A 69 6D 6D 79 00 - message ("jimmy") (0x40?)

        ),
        0x0F: Struct( # CameraPath
            "angle" / If(this._.m1.x2, ViewAngle32l), # f2322735000104000000021111111100
            # 0x4 does not consume any data? # f232273500010c000000050f0000
            "position" / If(this._.m1.x8, Vector3), # f2322735000104000000080000000000000000000000000000
            "rotation" / If(this._.m1.x8, Vector3), # ?????????????????????? WHAT THE FUCK This fixed the parsing completely, but makes no sense with the data from above...
            "entityIdAttachedTo" / If(this._.m1.x10, Int32ul), # If = 0, crashes. If = player's entity ID, works
            "m1x20" / If(this._.m1.x20, HexBytes(4)), # f232273500010400000020050000000000
            "m1x40" / If(this._.m1.x40, HexBytes(1)), # f232273500010400000040050000
            "m1x80" / If(this._.m1.x80, HexBytes(1)), # f232273500010400000080000000

            "includeFields" / Computed(lambda ctx: camera_path_field_stuff(ctx._.m1)),
            "m2" / If(this.includeFields, Mask8),

            "m2x1" / If(this.includeFields, If(this.m2.x1, HexBytes(1))), # f232273500010400000000010000
            "m2x2" / If(this.includeFields, If(this.m2.x2, HexBytes(1))), # f232273500010400000000020000
            "m2x4" / If(this.includeFields, If(this.m2.x4, HexBytes(1))), # f232273500010400000000040000

            # 0x8 and above do not consume additional data...
        ),
        0x10: Struct( # Vote
            "m1x2" / If(this._.m1.x2, HexBytes(1)), # f232273500010e00000002ff0000 10
            "createdAt" / If(this._.m1.x4, HexBytes(4)), # f232273500010e00000004ffffffff0000 10
            "creatorId" / If(this._.m1.x8, HexBytes(4)), # f232273500010e00000008ffffffff0000 10
            "votesYes" / If(this._.m1.x10, HexBytes(4)), # f232273500010e00000010ffffffff0000 10 # Related to the number of people voting Yes? The last 2 bytes (after endian) are used as a bitmask, a high bit means that player voted.
            "votesNo" / If(this._.m1.x20, HexBytes(4)), # f232273500010e00000020ffffffff0000 10 # Related to the number of people voting No?  The last 2 bytes (after endian) are used as a bitmask, a high bit means that player voted.
            "isPassed" / If(this._.m1.x40, HexBytes(1)), # f232273500010e00000040016767670000 10
            "isFailed" / If(this._.m1.x80, HexBytes(1)), # f232273500010e00000080016767670000 10

            "vote" / CString(ENC), # TODO: There seems to be more to this part...
        ),
        0x11: Struct( # Damage?
            "m1x2" / If(this._.m1.x2, HexBytes(1)),
            "m1x4" / If(this._.m1.x4, Vector3),
            "m1x8" / If(this._.m1.x8, HexBytes(4)),
            "senderId" / If(this._.m1.x10, Int32ul),
            "receiverId" / If(this._.m1.x20, Int32ul),
            "damageInfo" / If(this._.m1.x40, HexBytes(4)),
            # 0x80 does not consume any data # f232273500010e0000008000 11

            # See "Damage Entity.txt"
        ),
        0x12: Struct( # RaceStart
        	"isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 12
            # 0x04 and above do not consume any data # f232273500010e0000000400 12
        ),
        0x13: Struct( # RaceFinish
        	"isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 13
            # 0x04 and above do not consume any data # f232273500010e0000000400 13
        ),
        0x14: Struct( # WeaponRestrictor
            "isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 14
            "allowedWeaponMask" / If(this._.m1.x4, Int32ul) # TODO: Make this a mask
            # 0x08 and above do not consume any data # f232273500010e0000000800 14
        ),
        0x15: Struct( # Prefab
            "m1x2" / If(this._.m1.x2, HexBytes(1)),
            "isSelected" / If(this._.m1.x4, Int16ul),
            "position" / If(this._.m1.x8, Vector3),
            "angles" / If(this._.m1.x10, Vector3),
            "prefabName" / If(this._.m1.x20, CString(ENC)),
            "nextSubEntityId" / If(this._.m1.x40, Int32ul),
            "m1x80" / If(this._.m1.x80, Int32ul),

            "m2" / Mask8,

            "nextNormalEntityId" / If(this.m2.x1, Int32ul),
            "m2x2" / If(this.m2.x2, Int32ul),
        ) * registerPrefabSubEntities,
        0x16: Struct( # VolumeSelect
        	"isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 16
            # 0x04 and above do not consume any data # f232273500010e0000000400 16
        ),
        0x17: Struct( # WorkshopScreenshot
            "isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 17
            "position" / If(this._.m1.x4, Vector3),
            "angles" / If(this._.m1.x8, Vector3)
            # 0x10 and above do not consume any data # f232273500010e0000001000 17
        ),
        0x18: Struct( # ReflectionProbe
            "isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 18
            "position" / If(this._.m1.x4, Vector3),
            "angles" / If(this._.m1.x8, Vector3),
        ),
        0x19: Struct( # TriggerVolume
            "isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 19
            "linkOutOnEnter" / If(this._.m1.x4, CString(ENC)),
            "linkOutOnExit" / If(this._.m1.x8, CString(ENC))
            # 0x10 and above do not consume any data # f232273500010e0000001000
        ),
        0x1A: Struct( # Message
            "isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff0000 # If > 0, entity is selected and has the outline thing
            "position" / If(this._.m1.x4, Vector3),
            "angles" / If(this._.m1.x8, Vector3),
            "linkInDisplay" / If(this._.m1.x10, CString(ENC)),
            "linkInShow" / If(this._.m1.x20, CString(ENC)),
            "linkInHide" / If(this._.m1.x40, CString(ENC)),
            "message" / If(this._.m1.x80, CString(ENC)),

            "m2" / Mask8,

            "m2x1" / If(this.m2.x1, HexBytes(2)), # f232273500010e0000000001ffff00
            # 0x02 and above do not consume any data # f232273500010e000000000200
        ),
        0x1B: Struct( # Goal
            "isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 1B # If > 0, entity is selected and has the outline thing
            "position" / If(this._.m1.x4, Vector3),
            "angles" / If(this._.m1.x8, Vector3),
            "linkInDone" / If(this._.m1.x10, CString(ENC)),
            "message" / If(this._.m1.x20, CString(ENC)),
            "sortIndex" / If(this._.m1.x40, Float32l),
            "m1x80" / If(this._.m1.x80, HexBytes(1)), # f232273500010e00000080ff00 1B # Maybe isCompleted?
        ),
        0x1C: Struct( # Turret
            "m1x2" / If(this._.m1.x2, HexBytes(1)), # f232273500010e00000002ff0000
            "isSelected" / If(this._.m1.x4, Int16ul), # f232273500010e00000004ffff0000 # If > 0, turret is selected and has the outline thing
            "position" / If(this._.m1.x8, Vector3),
            "angles" / If(this._.m1.x10, Vector3),
            "weaponType" / If(this._.m1.x20, Int8ul),
            "m1x40" / If(this._.m1.x40, HexBytes(1)), # f232273500010e00000040ff0000
            "m1x80" / If(this._.m1.x80, HexBytes(1)), # f232273500010e00000080ff0000

            "m2" / Mask8,

            "health" / If(this.m2.x1, Int16ul),
            "m2x2" / If(this.m2.x2, Int32ul), # Timecode of some sort
            "m2x4" / If(this.m2.x4, HexBytes(4)), # f232273500010e0000000004ffffffff00
            # 0x08 and above do not consume any data # f232273500010e000000000800
        ),
        0x1D: Struct( # Shootable
            "isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff0000 # If > 0, entity is selected and has the outline thing
            "position" / If(this._.m1.x4, Vector3),
            "angles" / If(this._.m1.x8, Vector3),
            "linkOutDestroyed" / If(this._.m1.x10, CString(ENC)),
            "targetName" / If(this._.m1.x20, CString(ENC)),
            "dmgTaken" / If(this._.m1.x40, Int16ul),
            "m1x80" / If(this._.m1.x80, HexBytes(1)), # 06 00 00 00 C0 64 00 01 00 # Probably isDestroyed?

            "m2" / Mask8,

            "weaponType" / If(this.m2.x1, Int8ul),
            "m2x2" / If(this.m2.x2, HexBytes(4)), # f232273500010e0000000002ffffffff00
            "m2x4" / If(this.m2.x4, HexBytes(4)), # f232273500010e0000000004ffffffff00
            "m2x8" / If(this.m2.x8, HexBytes(4)), # f232273500010e0000000008ffffffff00
            "m2x10" / If(this.m2.x10, HexBytes(4)), # f232273500010e0000000010ffffffff00
            # 0x20 and above do not consume any data # f232273500010e000000002000
        ),
        0x1E: Struct( # Accumulator
            "isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 1E # If > 0, entity is selected and has the outline thing
            "position" / If(this._.m1.x4, Vector3),
            "angles" / If(this._.m1.x8, Vector3),
            "linkInCount" / If(this._.m1.x10, CString(ENC)),
            "linkOutDone" / If(this._.m1.x20, CString(ENC)),
            "countTarget" / If(this._.m1.x40, Int16ul),
            "m1x80" / If(this._.m1.x80, HexBytes(2)), # f232273500010e00000080ffff00 1E
        ),
        0x1F: Struct( # Exit
            "isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 1F # If > 0, entity is selected and has the outline thing
            "position" / If(this._.m1.x4, Vector3),
            "angles" / If(this._.m1.x8, Vector3),
            "linkInExit" / If(this._.m1.x10, CString(ENC)),
            # 0x20 and above do not consume any data # f232273500010e0000002000 1F
        ),
        0x20: Struct( # NavLink
            "isSelected" / If(this._.m1.x2, Int16ul), # f232273500010e00000002ffff00 20 # If > 0, entity is selected and has the outline thing
            "position" / If(this._.m1.x4, Vector3),
            "angles" / If(this._.m1.x8, Vector3),
            "name" / If(this._.m1.x10, CString(ENC)),
            "isStart" / If(this._.m1.x20, Flag),
            "isBidirectional" / If(this._.m1.x40, Flag),
            # 0x80 does not consume any data # f232273500010e0000008000 20
            # This means that the unknown bytes in the prefabEntity are really padding :) :) :) :) :) How the fuck do I implement that conditional Bool8 padding? :) :)
        )
    })),
)

TickPrefabChunk = Struct(
    "amount" / Rebuild(Int8ul, len_(this.prefabs)),
    "prefabs" / Prefab[this.amount],
)


TickEntityChunk = Struct(
    "amount" / Rebuild(Int8ul, len_(this.entities)),
    "entities" / Entity[this.amount],
)


TickBrushChunk = Struct(
    "amount" / Rebuild(Int8ul, len_(this.brushes)),
    "brushes" / Brush[this.amount]
)


Tick = Struct(
    "timecode" / Int32ul, # HEY YOU! THIS HAS TO STAY INT32UL BECAUSE allEntities() and other
                          # functions depend on comparing against this value!
    "prefabChunks" / RepeatUntil(lambda obj, lst, ctx: obj.amount < 0xFF, TickPrefabChunk),
    "entityChunks" / RepeatUntil(lambda obj, lst, ctx: obj.amount < 0xFF, TickEntityChunk),
    "brushChunks" / RepeatUntil(lambda obj, lst, ctx: obj.amount < 0xFF, TickBrushChunk),
)


ReplayHeaderPlayer = Struct(
    "name" / PaddedString(32, ENC_2),
    "score" / Int32sl,
    "team" / Int32sl,
    "steamId" / Int64ul
)


ReplayHeader = Struct(
    "tag" / HexBytes(4),
    "protocolVersion" / Int32ul,
    "supportedVersion" / Computed(Check(this.protocolVersion == 89)),
    "playerCount" / Int32ul,
    "markerCount" / Int32ul,
    "unknown1" / Int64ul,
    "workshopId" / Int64ul,
    "epochStartTime" / Int64ul,
    "epochStartTimeS" / Computed(lambda ctx: datetime.datetime.utcfromtimestamp(ctx.epochStartTime).strftime("%Y-%m-%d %H:%M:%S UTC")),
    "szGameMode" / PaddedString(64, ENC_2),
    "szMapTitle" / PaddedString(256, ENC_2),
    "szHostName" / PaddedString(256, ENC_2),
    "players" / ReplayHeaderPlayer[16],
)


Replay = Struct(
    "header" / ReplayHeader,
    "ticks" / GreedyRange(Tick)
)


def allPrefabs(replay, after=0):
    for tick in replay.ticks:
        if tick.timecode <= after:
            continue

        for chunk in tick.prefabChunks:
            for prefab in chunk.prefabs:
                yield tick.timecode, prefab


def allEntities(replay, after=0):
    for tick in replay.ticks:
        if tick.timecode <= after:
            continue

        for chunk in tick.entityChunks:
            for entity in chunk.entities:
                yield tick.timecode, entity


def allBrushes(replay, after=0):
    for tick in replay.ticks:
        if tick.timecode <= after:
            continue

        for chunk in tick.brushChunks:
            for brush in chunk.brushes:
                yield tick.timecode, brush


def allInitialEntities(replay):
    for chunk in replay.ticks[0].entityChunks:
        for entity in chunk.entities:
            if not entity.ent.destroy and entity.m1.x1:
                yield entity


def refactorChangeEntityIdsRaw(changes, entities, brushes):
    # Change all references to this entity ID to the new one
    # This includes entity creation, updates, attachedTos, damage entities, votes, chatmessages, projectiles, brushes, etc.
    for tc, entity in entities:
        if entity.ent.id in changes.keys():
            prev_id = copy.deepcopy(entity.ent.id)

            entity.ent.id = changes[entity.ent.id]

            if entity.entityType == 0x15: # Prefab
                diff = prev_id - entity.ent.id

                entity.fields.nextSubEntityId = entity.ent.id + 1
                entity.fields.nextNormalEntityId -= diff

        if entity.entityType in [0x04, 0x05, 0x06, 0x07, 0x08] and entity.fields.spawnedByEntityId in changes.keys():
            entity.fields.spawnedByEntityId = changes[entity.fields.spawnedByEntityId]

        if entity.entityType == 0x0E and entity.fields.senderId in changes.keys():
            entity.fields.senderId = changes[entity.fields.senderId]

        if entity.entityType == 0x0F and entity.fields.entityIdAttachedTo in changes.keys():
            entity.fields.entityIdAttachedTo = changes[entity.fields.entityIdAttachedTo]

        if entity.entityType == 0x10 and entity.fields.creatorId in changes.keys():
            entity.fields.creatorId = changes[entity.fields.creatorId]

        if entity.entityType == 0x11:
            if entity.fields.senderId in changes.keys():
                entity.fields.senderId = changes[entity.fields.senderId]

            if entity.fields.receiverId in changes.keys():
                entity.fields.receiverId = changes[entity.fields.receiverId]

    for tc, brush in brushes:
        if brush.entityIdAttachedTo in changes.keys():
            brush.entityIdAttachedTo = changes[brush.entityIdAttachedTo]


def refactorChangeEntityIds(changes, replay, after=0):
    # Change all references to this entity ID to the new one
    # This includes entity creation, updates, attachedTos, damage entities, votes, chatmessages, projectiles, brushes, etc.
    refactorChangeEntityIdsRaw(changes, list(allEntities(replay, after)), list(allBrushes(replay, after)))


def getReferencedEntityIds(replay):
    # Keep track of recipient entities that will be referenced by packets later on
    ids = []

    for tc,ent in allEntities(replay):
        # Don't keep WorldSpawn, it will always be replaced by the donor
        if ent.entityType == 0x00:
            continue

        if ent.ent.destroy or not ent.m1.x1:
            ids.append(ent.ent.id)

        # Also look out for references through other entities, such as cameraPath
        # For now, just keep cameraPath at all costs
        elif ent.entityType == 0x0F:
            ids.append(ent.ent.id)

    # Remove duplicates
    ids = list(dict.fromkeys(ids))

    return ids


def getEntity(id, replay):
    for chunk in replay.ticks[0].entityChunks:
        for entity in chunk:
            if entity.ent.id == id and not entity.ent.destroy and entity.m1.x1:
                return entity


def prepareLookups(replay):
    global ENTITY_LOOKUP

    for tc, entity in allEntities(replay):
        if not entity.ent.destroy and entity.m1.x1:
            ENTITY_LOOKUP[entity.ent.id] = entity.entityType


def build(rep: Replay):
    # Construct does not call process hooks while building, how nice :)
    prepareLookups(rep)

    return Replay.build(rep)
