import os
import re
import sys

import copy
import datetime

from replay import *


def extract_player_info(replay):
    player_ids = []

    for tick in replay.ticks:
        for chunk in tick.entityChunks:
            for entity in chunk.entities:
                if not entity.ent.destroy and entity.m1.x1 and entity.entityType == 0x02: # Needs short-circuiting
                    player_ids.append(entity.ent.id)

    info = {}

    for id in player_ids:
        info[id] = []

    for tick in replay.ticks:
        for chunk in tick.entityChunks:
            for entity in chunk.entities:
                if entity.ent.id in player_ids:
                    update = {}

                    if entity.fields.position:
                        update["position"] = [entity.fields.position.x, entity.fields.position.y, entity.fields.position.z]
                    if entity.fields.velocity:
                        update["velocity"] = [entity.fields.velocity.x, entity.fields.velocity.y, entity.fields.velocity.z]
                    if entity.fields.viewAngle:
                        update["viewAngle"] = [entity.fields.viewAngle.x, entity.fields.viewAngle.y]
                    if entity.fields.cameraRotation:
                        update["cameraRotation"] = [entity.fields.cameraRotation.x, entity.fields.cameraRotation.y, entity.fields.cameraRotation.z]

                    if len(update.keys()) > 0:
                        update["timecode"] = tick.timecode
                        info[entity.ent.id].append(update)

                        print(update)

    return info


def transplant_wrapper(donor_p, recipient_p, write_p):
    print("Reading donor replay")
    with open(donor_p, "rb") as donor_f:
        donor_d = bytearray(donor_f.read())
    donor = Replay.parse(donor_d)

    print("Reading recipient replay")
    with open(recipient_p, "rb") as recipient_f:
        recipient_d = bytearray(recipient_f.read())
    recipient = Replay.parse(recipient_d)

    out = transplant(donor, recipient)

    # Set workshopId to 0 to force Reflex to rely on the replay's internal map and entity information.
    # Also allows moviemaker to provide their own lightmap
    out.header.workshopId = 0

    print("Building and writing edited replay")

    with open(write_p, "wb+") as write_f:
        write_f.write(build(out))

    return out


def transplant(donor, recipient):
    # The recipient will keep all initial entities that are updated by packets later on
    rec_keep_ent_ids = getReferencedEntityIds(recipient)
    rec_ents = {entity.ent.id:entity for entity in allInitialEntities(recipient) if entity.ent.id in rec_keep_ent_ids}

    # We will keep track of any ID changes that will be made to the entities that the recipient will keep
    rec_id_changes = {}

    # We also have to know all prefabs
    rec_prefabs = {prefab.prefabName:prefab for tc, prefab in allPrefabs(recipient)}

    # The donor will donate all entities that are not updated by packets later on TODO: Why not all entities except the obvious no-gos?
    donor_keep_ent_ids = getReferencedEntityIds(donor)
    donor_ents = {entity.ent.id:entity for entity in allInitialEntities(donor) if entity.ent.id not in donor_keep_ent_ids}

    # We will also keep track of any ID changes that will be made to the entities that the donor will donate
    donor_id_changes = {}

    # We also have to know all prefabs at all times
    donor_prefabs = {prefab.prefabName:prefab for tc, prefab in allPrefabs(donor)}

    num_entities_total = len(rec_ents.keys()) + len(donor_ents.keys())
    new_entities = []

    id = 0

    while len(rec_ents.keys()) + len(donor_ents.keys()) > 0:
        # If ID is reserved by recipient entity, insert recipient entity instead
        if id in rec_keep_ent_ids and id in rec_ents.keys():
            print("Adding reserved recipient entity", id)
            entity = rec_ents[id]

            new_entities.append(entity)

            del rec_ents[id]

            # Adjust ID for next entity
            if entity.entityType == 0x15: # Prefab
                id += rec_prefabs[entity.fields.prefabName].numEntities

            id += 1

        elif len(donor_ents.keys()) > 0:
            print("Adding donor entity", id)
            entity_id, entity = next(iter(donor_ents.items()))

            if id != entity_id:
                donor_id_changes[entity_id] = id

            # Adjust ID for next entity
            if entity.entityType == 0x15: # Prefab
                id += donor_prefabs[entity.fields.prefabName].numEntities

            id += 1

            new_entities.append(entity)

            del donor_ents[entity_id]
        elif len(rec_ents.keys()) > 0:
            print("Adding remaining recipient entity", id)
            entity_id, entity = next(iter(rec_ents.items()))

            if id != entity_id:
                rec_id_changes[entity_id] = id

            # Adjust ID for next entity
            if entity.entityType == 0x15: # Prefab
                id += rec_prefabs[entity.fields.prefabName].numEntities

            id += 1

            new_entities.append(entity)

            del rec_ents[entity_id]

    # Adjust tail entities
    # All that matters is that these entities are created after the first tick
    # ALL of those entities need to be adjusted
    for tc, entity in allEntities(recipient, recipient.ticks[0].timecode):
        if not entity.ent.destroy and entity.m1.x1:
            rec_id_changes[entity.ent.id] = id

            # Adjust ID for next entity
            if entity.entityType == 0x15: # Prefab
                id += rec_prefabs[entity.fields.prefabName].numEntities

            id += 1

    # Refactor the initial replay objects
    # This will refactor all entities in new_entities, since they were passed by reference
    refactorChangeEntityIds(rec_id_changes, recipient)
    refactorChangeEntityIds(donor_id_changes, donor)

    print("Changing initial prefab and brush chunks")

    recipient.ticks[0].prefabChunks = donor.ticks[0].prefabChunks
    recipient.ticks[0].brushChunks = donor.ticks[0].brushChunks

    recipient.ticks[0].entityChunks = []

    print("Converting new entities to chunks")

    # Convert new_entities to chunks...
    while len(new_entities) > 0xFF:
        recipient.ticks[0].entityChunks.append(TickEntityChunk.parse(TickEntityChunk.build({"amount": 0xFF, "entities": new_entities[:0xFF]})))
        new_entities = new_entities[0xFF:]

    recipient.ticks[0].entityChunks.append(TickEntityChunk.parse(TickEntityChunk.build({"amount": len(new_entities), "entities": new_entities})))

    # DEBUG: Limit number of ticks to diagnose crash
    #recipient.ticks = recipient.ticks[:1255]

    return recipient


if __name__ == "__main__":
    if len(sys.argv) == 4:
        donor_p = sys.argv[1]
        recipient_p = sys.argv[2]
        out_p = sys.argv[3]

    else:
        print("Make sure to avoid spaces in your file paths!")

        donor_p = input("Path to donor: ")
        recipient_p = input("Path to recipient: ")
        out_name = input("Output file name: ")

        if out_name == "":
            out_name = "transplant.rep"

        if not out_name.endswith(".rep"):
            out_name += ".rep"

        out_p = os.path.join(os.path.dirname(recipient_p), out_name)

    transplant_wrapper(donor_p, recipient_p, out_p)
