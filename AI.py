import math
import random

import statuses
import typeData
import moves

from moves import load_moves, ModifyStatStageEffect
from pokemon import Nature, PokemonInstance, load_pokemon_templates,NatureList
from team import Team

"""HouseKeeping for James' Sake
    Fair few errors -
     UnImplememted - Entry Hazards and Weather Effects
     Needs renaming - All Stat changes, 
     Needs rework - Speed Stat calculator"""

def find_best_move(AI_Pokemon,AI_Team,Player_Pokemon,Move_List):
    """From the usable moves, finds the best one"""
    #Check each move, build a score, then compare scores and select the move with highest score
    damage_list = []
    for move in Move_List:
        move = move.move
        #I expect this to cause an error for status moves but we try
        if moves.DamageEffect not in move.effects: #missing multihit or fixed
            damage = 0
        else: damage = move.calculate_damage(user=AI_Pokemon,target=Player_Pokemon,move_type=move.move_type)
        damage_list.append(damage)
    #We will do the same for player
    Player_damage_list = []
    for move in Player_Pokemon.known_moves:
        move = move.move
        #I expect this to cause an error for status moves but we try
        if moves.DamageEffect not in move.effects: #missing multihit or fixed
            damage = 0
        else: damage,type_advantage = move.calculate_damage(user=Player_Pokemon,target=AI_Pokemon,move_type=move.move_type)
        Player_damage_list.append(damage)
    #now we check scores
    movescores = []
    for i in range(0,len(Move_List)):
        move = Move_List[i]
        move = move.move
        score = check_move_score(Player_Pokemon,AI_Pokemon,move,damage_list,damage_list[i],Player_damage_list,Move_List)
        print("PASSED")
        movescores.append(score)
        if max(movescores) == score:
            bestMove = move
    print(bestMove)
    return bestMove.name

def should_ai_recover(move): #low time making a random check for now
    return random.randint(0,49) == 49

def obvious_bad_move(Player_Pokemon,AI_Pokemon,Move,type_advantage,Damage_List,Damage,Player_Damage_list,Move_List):
    #Status Effects
    if AI_Pokemon.has_major_status:
        if Move.name in ["Inferno","Wilo","Psycho Shift","Sizzly Slide","Barb Barrage","Dire Claw","Tri Attack","G-Max Befuddle","Poison Gas","Poison Powder","Sludge","Smog","Toxic","Glare","Thunder Wave","Nuzzle","Stun Spore","Dark Void","Grass Whistle","Hypnosis","Lovely Kiss","Sleep Powder","Sleep Spore","Yawn"]:
            move_score = -20
    #Buffs
    elif (AI_Pokemon.StatStages.attack == 6 and Move.StatusAtt > 0) or (AI_Pokemon.StatStages.defense == 6 and Move.StatusDef > 0) or (AI_Pokemon.StatStages.special_attack == 6 and Move.StatusSpA > 0) or (AI_Pokemon.StatStages.special_defense == 6 and Move.StatusSpD > 0) or (AI_Pokemon.StatStages.speed == 6 and Move.StatusSpe > 0) or (AI_Pokemon.StatStages.evasion == 6 and Move.StatusEva > 0):
        move_score = -20
    #Repeat Effects
    #We get there when we get there

def check_move_score(Player_Pokemon,AI_Pokemon,Move,Damage_List,Damage,Player_Damage_list,Move_List):
    #The meat of the bones
    isHighestDamage = (max(Damage_List) == Damage) # fix this, either index what move does what damage or smth else
    isFaster = (AI_Pokemon.get_effective_stat(stat_name = "speed" ) >= Player_Pokemon.get_effective_stat(stat_name = "speed"))
    # ignoring held items for now, gen 9 has some high crit things give +1 or +2 stage, our data doesn't support so ignore for now, focus energy too
    isPriority = (Move.priority > 0)
    isAntiPriority = (Move.priority < 0)  # note we aren't tracking the players priority. smth we can improve on

    isKillMove = (Damage >= Player_Pokemon.current_hp) #This is a print, change this so we get the value of hp not text
    isAnyMoveKill = (max(Damage_List) >= Player_Pokemon.current_hp)
    isAnyMove3HitKill = (max(Damage_List)-1 >= Player_Pokemon.current_hp//3)
    is2HitKillMove = (Damage >= math.ceil(Player_Pokemon.current_hp//2)+1) #maybe minor rounding error

    isMeDead = (max(Player_Damage_list) >= AI_Pokemon.current_hp)
    is2HitMeDead = (max(Player_Damage_list) >= math.ceil(AI_Pokemon.current_hp//2)+1)

    isFirstMove = True #not implemented yet
    LastPlayerMove = "" #not implemented yet
    LastAIMove = "" #not implemented yet
    Incapacited = ("Frozen" in AI_Pokemon.status_effects or "Sleep" in AI_Pokemon.status_effects or "Recharging" in AI_Pokemon.status_effects)
    Trapping_Moves = ["Anchor Shot","Block","Fairy Lock","G-Max Terror","Ingrain","Jaw Lock","Mean Look","No Retreat","OctoLock","Shadow Hold","Spider Web","Spirit Shackle","Thousand Waves"]
    Binding_Moves = ["Bound","Bind","Clamp","Fire Spin","G-Max Centiferno","G-Max Sandblast","Infestion","Magma Storm","Sand Tomb","Snap Trap","Thunder Cage","Whirlpool","Wrap"]
    entry_hazard = []  #not implemented yet
    currentTerrain = []  ##not implemented yet

    move_score = 0
    for effect in Move.effects:
        if type(effect) == moves.DamageEffect:
            if Move.name in ["Explosion","Self Destruct","Misty Explosion"]:
                if AI_Pokemon.current_hp < AI_Pokemon.max_hp / 10:
                    move_score +=10
                elif AI_Pokemon.current_hp < AI_Pokemon.max_hp / 3 and random.randint(1,10) >= 3:
                    move_score +=8
                elif AI_Pokemon.current_hp < (2*AI_Pokemon.max_hp) / 3 and random.randint(0,1) == 1:
                    move_score += 7
                elif random.randint(1,20) == 20: move_score += 5
                else: pass

        #Moxie,Beast Boost, Chilling Neigh, Grim Neigh check

            elif isHighestDamage or Move.name in Trapping_Moves or Move.name in Binding_Moves or isKillMove:
                if random.randint(0,4) == 4: move_score = 8
                else: move_score = 6
                if isKillMove:
                    if isFaster or (not isFaster and isPriority):
                        move_score += 6
                    else:
                        move_score += 3

            if isMeDead and isPriority:
                move_score += 11

            if Move.name == "Memento":
                if AI_Pokemon.current_hp < AI_Pokemon.max_hp / 10:
                    move_score +=16
                elif AI_Pokemon.current_hp < AI_Pokemon.max_hp / 3 and random.randint(1,10) >= 3:
                    move_score +=14
                elif AI_Pokemon.current_hp < (2*AI_Pokemon.max_hp) / 3 and random.randint(0,1) == 1:
                    move_score += 13
                elif random.randint(1,20) == 20: move_score += 13
                else: move_score += 6

            #Xin does the rest, General setup

            if Move.name == "Future Sight":
                if isFaster and isMeDead:
                    move_score += 8
                else:
                    move_score += 6

            if Move.name == "Sucker Punch":
                if LastAIMove == Move.name:
                    if random.randint(0,1)==1:
                        move_score = -20

            if Move.name == "Pursuit":
                if isKillMove:
                    move_score += 10
                else:
                    if Player_Pokemon.current_hp/Player_Pokemon.max_hp <= 0.2:
                        move_score += 10
                    elif Player_Pokemon.current_hp/Player_Pokemon.max_hp <= 0.4:
                        if random.randint(0,1)==1:
                            move_score += 8
                if isFaster:
                    move_score += 3

            if Move.name == "Fell Stinger":
                if AI_Pokemon.StatStages.attack < 6 and isKillMove:
                    if isFaster:
                        if random.randint(0,4)==4:
                            move_score = 21
                        else:
                            move_score = 23
                    else:
                        if random.randint(0,4)==4:
                            move_score = 15
                        else:
                            move_score = 17
                # otherwise treated as a normal damaging move

            if Move.name == "Rollout":
                move_score += 7

            if Move.name == "Stealth Rock":
                if random.randint(0,3)==3:
                    if isFirstMove:
                        move_score += 9
                    else:
                        move_score += 7
                else:
                    if isFirstMove:
                        move_score += 8
                    else:
                        move_score += 6

            if Move.name == "Spikes" or Move.name == "Toxic Spikes":
                if random.randint(0,3)==3:
                    if isFirstMove:
                        move_score += 9
                    else:
                        move_score += 7
                else:
                    if isFirstMove:
                        move_score += 8
                    else:
                        move_score += 6
                if "Spike" in entry_hazard or "toxic spike": # fix when  terrain works
                    move_score -= 1

            if Move.name == "Sticky Web":
                if isFirstMove:
                    if random.randint(0,3)==3:
                        move_score += 12
                    else:
                        move_score += 9
                else:
                    if random.randint(0,3)==3:
                        move_score += 9
                    else:
                        move_score += 6

            if Move.name == "Protect" or Move.name == "King's Shield":
                move_score += 6

                statusList = ("Posion", "Burn", "Cursed", "Infatuated", "Perish Songed", "Leech Seeded", "Yawned")
                hasListStatusAI = False
                hasListStatusPlayer = False
                for status in statusList:
                    if status in AI_Pokemon.status_effects:
                        hasListStatusAI = True
                    if status in Player_Pokemon.status_effects :
                        hasListStatusPlayer = True
                if hasListStatusAI:
                    move_score -= 2
                if hasListStatusPlayer:
                    move_score += 1

                if isFirstMove:
                    move_score -= 1

                # AI will not use this if they die to secondary damage afterwards

                if LastAIMove == "Protect" or LastAIMove == "King's Shield":
                    if random.randint(0,1) == 1:
                        move_score = -20

            # AI will not use this if both previous turns used this

        # Fling

        # Role Play

    if Move.name == "Imprison":
        inCommon = False
        for playerMove in Player_Pokemon.movelist:
            for AIMove in Move_List:
                if playerMove == AIMove:
                    inCommon = True
        if inCommon:
            move_score += 9
        else:
            move_score = -20

    if Move.name == "Tailwind":
        if isFaster:
            move_score += 5
        else:
            move_score += 9

    if Move.name == "Trick Room":
        if isFaster:
            move_score += 5
        else:
            move_score += 10

        if currentTerrain == "Trick Room":
            move_score = -20
            # If trick room is already up, dont use

    if Move.name == "Fake Out":
        if isFirstMove:
                move_score += 9
            # Also should not target shield dust/ inner focus but those are abilities

    if Move.name == "Final Gambit":
        if isFaster and AI_Pokemon.current_hp > Player_Pokemon.current_hp:
            move_score += 8
        elif isFaster and isMeDead:
            move_score += 7
        else:
            move_score += 6

    if currentTerrain == "Electric" or currentTerrain == "Psychic" or currentTerrain == "Grassy" or currentTerrain == "Misty":
        move_score += 8

    if Move.name == "Light Screen" or Move.name == "Reflect":
        move_score += 6
        if random.randint(0,1)==1:
             move_score += 1

    if Move.name == "Substitute":
        move_score += 6

        if "Asleep" in Player_Pokemon.status_effects:
            move_score += 2
        if "Leech Seeded" in Player_Pokemon.status_effects  and isFaster:
            move_score += 2
        if random.randint(0,1)==1:
            move_score -= 1

            # if checkType(playerMoveList, "Sound"): # Need to get the sound attribute working
            #     moveScore -= 8
            # if currentHealth <= 50:
            #     moveScore = -20

    if Move.name == "Will-O-Wisp":
        move_score += 6

        if random.randint(0,2)==2:
            if "Hex" in Move_List:
                    move_score += 2

    if Move.name == "Switcheroo" or Move.name == "Trick":
        move_score -= 2
            # Has item interactions, should be +5 but no items so temp -2

    if Move.name == "Yawn" or Move.name == "Dark Void" or Move.name == "Sing":
        move_score += 6

        if random.randint(0,3)==3:
            # should check if player can be put to sleep, this is handled by dunbmoves
            move_score += 1

            aiHasMove = False
            playerHasMove = False

            for move in Move_List:
                if move == "Dream Eater" or move == "Nightmare":
                    aiHasMove = True
                if move == "Hex":
                    move_score += 1
            for move in Player_Pokemon.movelist:
                if move == "Snore" or move == "Pillow Talk":
                    playerHasMove = True

            if aiHasMove and not playerHasMove:
                move_score += 1

    for effect in Move.effects:
        if type(effect) == moves.ApplyStatusEffect:
            if type(effect.status_factory) ==  statuses.Poison:
                move_score += 6

                if random.randint(0,4)>=3:
                    if not isKillMove:
                        if "Poison" not in Player_Pokemon.types and Player_Pokemon.current_hp/Player_Pokemon.max_hp > 0.20:  # checks if player can be poisoned
                            possibleMove = False
                            for move in Move_List:
                                if move == "Hex" or move == "Venom Drench" or move == "Venoshock":
                                    possibleMove = True
                            damagingMove = False
                            for move in Player_Pokemon.movelist:
                                if move.move_types == "Damaging":  # rewrite to check for damage
                                    damagingMove = True
                            if possibleMove and not damagingMove:
                                move_score += 2
    if Move.name == "Destiny Bond":
        if isFaster and isMeDead:
            move_score = 7
        elif random.randint(0, 1) == 1:
            move_score = 6
        else:
            move_score = 5

    elif Move.name == "Taunt":
        for move in Player_Pokemon.movelist:
            if move == "Trick Room" and not currentTerrain == "Trick Room":
                move_score += 9
            elif isFaster:
                for move in Player_Pokemon.movelist:
                    if move == "Defog" and "Aurora Veil" in Player_Pokemon.status_effects:
                        move_score += 9
            else:
                move_score += 5

    elif Move.name == "Encore":
        encoreEncouraged = (LastPlayerMove.effects[0][
                                "Catagory"] == "Status")  # The AI looks at the target's last used move and checks if it is one that should be Encored.
        # The list of moves that should be Encored is very long and I will not be listing them all here,
        # but it mostly boils down to non-damaging moves
        if isFaster and encoreEncouraged:
            move_score += 7
        else:
            if random.randint(0, 1) == 1:
                move_score += 6
            else:
                move_score += 5
        if isFirstMove:
            move_score = -20

    elif Move.name == "Counter" or Move.name == "Mirror Coat":
        move_score += 6

        moveExist = False
        for move in Move_List:
            if move == "Sturdy" or move == "Focus Sash":
                moveExist = True
        if isMeDead and moveExist and AI_Pokemon.current_hp == AI_Pokemon.max_hp:  # target only has moves of the corresponding split (e.g. only physical moves for Counter scoring) not sure what this means
            move_score += 2

        elif not isMeDead:  # Same split thing as above
            if random.randint(0, 4) == 4:
                move_score += 2
        if isFaster:
            move_score -= 1
        for move in Player_Pokemon.movelist:
            if move.category == "Status":
                move_score -= 1

    elif Move.name == "Recover" or Move.name == "Slack Off" or Move.name == "Heal Order" or Move.name == "Roost" or Move.name == "Strength Sap" or Move.name == "Morning Sun" or Move.name == "Synthesis" or Move.name == "Moonlight":
        if should_ai_recover("standard"):
            move_score += 7
        else:
            move_score += 5

        if AI_Pokemon.current_hp >= AI_Pokemon.max_hp:
            move_score = -20
        elif AI_Pokemon.current_hp * 0.85 >= AI_Pokemon.max_hp:
            move_score -= 6

    elif Move.name == "Morning Sun" or Move.name == "Synthesis" or Move.name == "Moonlight":
        pass  # fill with weather based logic

    elif Move.name == "Rest":
        if should_ai_recover("rest"):
            tempCondition = False
            for move in Move_List:
                if move == "Sleep Talk" or move == "Snore":
                    tempCondition = True
            if tempCondition:
                move_score += 8
            else:
                move_score += 7
        else:
            move_score += 5

    for effect in Move.effects:
        if type(effect) == ModifyStatStageEffect:
            if effect.target_side == "target":
                if effect.stat_name == "speed" and effect.amount <= -1:  # Could be iffy
                    if isHighestDamage:
                        pass
                    elif not isFaster:
                        move_score = 6
                    else:
                        move_score = 5

                # Assuming guarrented effect, need a way to check this

                if effect.stat_name == "attack" or effect.stat_name == "special attack" and effect.amount <= -1:
                    if isHighestDamage:
                        pass
                elif not isFaster:
                    move_score += 6
                else:
                    move_score += 5

                if effect.stat_name == "special defence" and effect.amount <= -2:
                    move_score += 6
            elif effect.target_side == "user":
                if (effect.stat_name == "attack" or effect.stat_name == "special attack" or effect.stat_name == "speed") and effect.amount >= 1: #Offensive setup:
                    move_score = 6
                    if Incapacited:
                        move_score += 3
                    if is2HitMeDead and not isFaster:
                        move_score -= 5

                elif (effect.stat_name == "defence" or effect.stat_name == "special defence") and effect.amount >= 1:
                    move_score = 6
                    if Incapacited:
                        move_score += 2
                    if is2HitMeDead and not isFaster:
                        move_score -= 5
                    if AI_Pokemon.StatStages.defense < 2 and AI_Pokemon.StatStages.special_defense < 2:
                        move_score += 2

                if Move.name in ["Agility","Rock Polish","Autotomize"]:
                    if not isFaster:
                        move_score += 7
                    else: move_score = -20

                elif Move.name in ["Tail Glow"," Nasty Plot","Work Up"]:
                    move_score = 6
                    if Incapacited:
                        move_score += 3
                    else:
                        if not isAnyMove3HitKill:
                            move_score += 1
                            if isFaster: move_score += 1
                    if is2HitMeDead and not isFaster:
                        move_score -= 5
                    if AI_Pokemon.StatStages.special_attack >= 2:
                        move_score -= 2

                elif Move.name == "Shell Smash":
                    move_score = 6
                    if Incapacited:
                        move_score += 3
                    if is2HitMeDead and not isFaster:
                        move_score -= 2
                    else: move_score += 2
                    if AI_Pokemon.StatStages.attack > 0 or AI_Pokemon.StatStages.special_attack >3:
                        move_score -= 20

                elif Move.name  == "Belly Drum":
                    if Incapacited:
                        move_score = 9
                    elif max(Player_Damage_list) < AI_Pokemon.current_hp - AI_Pokemon.max_hp/2:
                        move_score = 8
                    else:
                        move_score = 4

                elif Move.name in ["Focus Energy","Laser Focus"]: # no items or abilities to consider
                    move_score = 6

                elif Move.name in ["Coaching","Meteor Beam"]: #doubles or requires items
                    move_score = -20
            if isAnyMoveKill and not isKillMove: move_score -= 20
    return move_score


def shouldswap(AI_Pokemon,Player_Pokemon,AI_Team,Damage_List,Player_Damage_List,Move_List):
    isFaster = (AI_Pokemon.speed >= Player_Pokemon.speed)
    isKillMove = (max(Damage_List) >= Player_Pokemon.current_hp)  # This is a print, change this so we get the value of hp not text
    isMeDead = (max(Player_Damage_List) >= AI_Pokemon.current_hp)
    isFainted = AI_Pokemon.current_hp <= 0
    Trapping_Moves = ["Anchor Shot", "Block", "Fairy Lock", "G-Max Terror", "Ingrain", "Jaw Lock", "Mean Look",
                      "No Retreat", "OctoLock", "Shadow Hold", "Spider Web", "Spirit Shackle", "Thousand Waves"]
    Binding_Moves = ["Bound", "Bind", "Clamp", "Fire Spin", "G-Max Centiferno", "G-Max Sandblast", "Infestion",
                     "Magma Storm", "Sand Tomb", "Snap Trap", "Thunder Cage", "Whirlpool", "Wrap"]
    entry_hazard = []  # not implemented
    currentTerrain = [] #as above

    base = 0
    if isMeDead and not isFaster:
        base = 15
    elif isKillMove and (not isMeDead or isFaster):
        base = -100
    AI_Pokemon_List = AI_Team.members
    entry_hazard = []
    if entry_hazard != []:
        base -= 2
    Scores = [base,base,base,base,base,base]
    if not ((AI_Pokemon.StatStages.attack == 0) and (AI_Pokemon.StatStages.defense == 0) and (AI_Pokemon.StatStages.special_attack== 0) and (AI_Pokemon.StatStages.special_defense == 0) and (AI_Pokemon.StatStages.speed == 0) and (AI_Pokemon.StatStages.evasion == 0)):
        for i in range(0,len(Scores)): Scores[i] += sum(AI_Pokemon.StatStages.attack+AI_Pokemon.StatStages.defense+AI_Pokemon.StatStages.special_attack+AI_Pokemon.StatStages.special_defense+AI_Pokemon.StatStages.speed+AI_Pokemon.StatStages.evasion)*2
    #Defensive swap

    Defence_Check_All = False #The case when there is no good swap defensively
    for ai_pokemon in AI_Pokemon_List:
        if typeData.get_type_multiplier("Rock", ai_pokemon.types) > 1 and "Stealth Rock" in entry_hazard:
             Scores[AI_Pokemon_List.index(ai_pokemon)] -= 4
        if "Poison" in ai_pokemon.types and "Toxic Spikes" in entry_hazard:
             Scores[AI_Pokemon_List.index(ai_pokemon)] += 2
        elif "Toxic Spikes" in entry_hazard:
            Scores[AI_Pokemon_List.index(ai_pokemon)] -= 3
        if "Flying" in ai_pokemon.types and ("Spikes" in entry_hazard or "Toxic Spikes" in entry_hazard):
           Scores[AI_Pokemon_List.index(ai_pokemon)] += 2

        Defence_Check = True
        Offence_Check = False
        Offence_2Hit = False

        for type in Player_Pokemon.types:
            if typeData.get_type_multiplier(type, ai_pokemon.types) >= 1 and ai_pokemon.current_hp/ai_pokemon.max_hp >= 0.5:
                Defence_Check = False

        for move in ai_pokemon.movelist:
            if moves.DamageEffect not in move.effects:  # missing multihit or fixed
                damage = 0
            else:
                damage = move.calculate_damage(user=AI_Pokemon, target=Player_Pokemon, move_type=move.move_type)
            if damage >= Player_Pokemon.current_hp:
                Offence_Check = True
            if damage*2 >= Player_Pokemon.current_hp:
                Offence_2Hit = True

        if Offence_Check == True:
            Scores[AI_Pokemon_List.index(ai_pokemon)] += 9
        elif Offence_2Hit == True:
            Scores[AI_Pokemon_List.index(ai_pokemon)] += 6
        else: pass

        if Defence_Check == True:
            Scores[AI_Pokemon_List.index(ai_pokemon)] += 15
            Defence_Check_All = True

    if not Defence_Check_All:
        for i in range(0,len(Scores)): Scores[i] -= 20

    #ok finally do we switch or not cuh
    #probably check highest scorer and then if it passes a good threashold then we chilling
    if max(Scores) >= 15:
        return AI_Pokemon_List[Scores.index(max(Scores))]
    else: return AI_Pokemon







#issues asside from no items and abilities
"""We need a way to determine bad moves and not do them. When i say bad moves I mean bad moves which are
obvious like Toxic on a poison type or thunderwave on a already paralysed pokemon.
Switch AI, we need to determine what pokemon we swap into"""


#How can we improve?
