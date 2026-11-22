"""Source of truth for the named NPC roster. Run: python tools/build_npcs.py  -> data/npcs.json

Rows are compact so the whole roster can be reviewed at a glance.
personality = (friendliness, aggression, confidence, intelligence, honesty, greed, loyalty, sociability) 0-10
attributes  = (strength, speed, health, dexterity)
"""
import json
import os

P = ("friendliness", "aggression", "confidence", "intelligence", "honesty", "greed", "loyalty", "sociability")
A = ("strength", "speed", "health", "dexterity")

ROWS = [
 # id, name, race, pronouns, age, occupation, home, faction, schedule, personality, attrs, skills, equipment, background, greeting, likes, dislikes, romance, recruit, extra
 ("hessa", "Hessa Moorweld", "human", "she/her", 52, "Provisioner", "brackenford", "crown", "merchant", (8,2,6,6,8,3,8,7), (12,9,14,10), {"trading":30,"gathering":25}, ["dagger_rustite"],
  "Widowed farmer who turned her late husband's grain shed into the village provision shop. Knows everyone's business and feeds anyone who's hungry.",
  "Morning, love. You look like you could use a proper meal.", ["food","herbs"], ["drink","weapons"], False,
  {"friendship":45, "favor":"hessa_minder", "favor_desc":"Find someone to mind her shop while she's away (pay 100 marks for a hand)."}, {"shop":"provisioner"}),
 ("tobin", "Tobin Reed", "human", "he/him", 19, "Farmhand", "brackenford", None, "worker", (8,3,4,5,7,2,7,8), (11,12,12,9), {"gathering":15,"melee":5}, ["axe_rustite"],
  "Bored out of his mind hauling grain sacks. Dreams of the caravan roads and keeps a notebook of every traveler's story.",
  "You're not from around here! Where've you been? Anywhere interesting?", ["weapons","jewelry"], ["food"], True, {"friendship":15}, {}),
 ("garrow", "Old Garrow", "human", "he/him", 67, "Retired Soldier", "brackenford", "crown", "elder", (4,5,7,7,9,2,9,3), (16,6,15,14), {"melee":45,"blocking":40}, ["longsword_greyvein"],
  "Fought in the Thornblood wars forty years ago and still walks the fence line at dawn. Thinks young people are soft, and is usually right.",
  "Hmph. Another wanderer. Can you even hold a sword?", ["weapons","drink"], ["jewelry"], False,
  {"respect":40, "favor":"garrow_spar", "favor_desc":"Prove yourself in a sparring match."}, {}),
 ("wren", "Wren Ashby", "sylth", "she/her", 24, "Herbalist", "brackenford", None, "worker", (9,1,3,7,9,2,7,4), (7,13,9,14), {"gathering":30,"magic":15,"crafting":20}, ["dagger_rustite"],
  "Settled in Brackenford after her wandering family moved on without her. Grows medicinal herbs behind the inn and patches up every scraped knee in the village.",
  "Oh! Hello. Are you hurt? You look a little scuffed.", ["herbs","books"], ["weapons"], True,
  {"friendship":35, "favor":"wren_mirelight", "favor_desc":"Bring her 3 Mirelight Herbs from the bog."}, {}),
 ("bram", "Bram Tull", "human", "he/him", 45, "Innkeeper", "brackenford", None, "merchant", (7,3,6,5,5,7,5,9), (13,8,14,8), {"trading":35}, [],
  "Runs The Leaning Plough. Jovial, loud, and always counting coins under the bar.",
  "Welcome to The Leaning Plough! Bed's 8 marks, ale's 3, gossip's free.", ["drink","jewelry"], ["herbs"], False,
  {"gold":250, "favor_desc":"Pay for a replacement innkeeper."}, {"shop":"inn"}),

 ("queen_aldra", "Queen Aldra Venn", "human", "she/her", 48, "Queen of Velmora", "velmora", "crown", "noble", (4,5,9,9,6,4,7,5), (10,9,12,11), {"trading":40,"melee":20}, ["longsword_sunsilver"],
  "Took the throne after her brother died in the Thornblood wars. Pragmatic, tired, and convinced the Hollow will be the end of the realm if no one stops them.",
  "Speak plainly. My time is the realm's.", ["books","jewelry"], ["hide"], False,
  {"rep":{"crown":80}, "respect":70, "friendship":50, "favor":"aldra_succession", "favor_desc":"Destroy the Hollow and secure a successor for the throne."}, {"leader":True}),
 ("ilsa", "Captain Ilsa Varn", "human", "she/her", 36, "Guard Captain", "velmora", "crown", "guard", (5,6,8,7,8,2,9,4), (18,13,18,15), {"melee":50,"blocking":45,"dodging":25}, ["longsword_greyvein"],
  "Rose from gate guard to captain of the city watch. Hates corruption more than she hates bandits.",
  "State your business in Velmora, traveler.", ["weapons","tools"], ["drink"], True, {"rep":{"crown":40}, "respect":40}, {}),
 ("corwin", "Corwin Hale", "human", "he/him", 29, "Disgraced Noble", "velmora", None, "night_owl", (7,3,7,6,2,7,3,9), (10,12,11,15), {"trading":30,"dodging":20,"melee":15}, ["shortsword_greyvein"],
  "Third son of a minor house, disowned after a gambling scandal. Charming, broke, and very good at talking his way out of trouble.",
  "Well! A new face. Tell me, friend, do you play cards?", ["jewelry","drink"], ["tools"], True, {"gold":150}, {}),
 ("marta", "Marta Quill", "human", "she/her", 41, "Royal Archivist", "velmora", "crown", "scholar", (6,1,5,10,9,2,7,4), (6,8,10,12), {"magic":20,"trading":15}, [],
  "Keeps the Crown's records and secretly writes an unauthorised history of the vanished builders.",
  "Mind the scrolls. Oh - are you an adventurer? Have you seen any ruins?", ["books","relic"], ["weapons"], False,
  {"friendship":30, "favor":"marta_relic", "favor_desc":"Bring her a Relic Shard from the ruins."}, {}),
 ("brask", "Sergeant Brask", "kethari", "he/him", 39, "Crown Sergeant", "velmora", "crown", "guard", (5,6,7,4,8,3,9,5), (22,8,22,11), {"melee":40,"blocking":35}, ["hammer_greyvein"],
  "A Kethari who joined the Crown army to send money home to Cinderdeep. Blunt, dependable, and owed several years of back pay.",
  "Hah. You've got a miner's hands. Or you will.", ["ore","drink"], ["magic"], False,
  {"rep":{"crown":25}, "gold":200, "favor_desc":"Buy out the rest of his service contract."}, {}),
 ("lysa", "Lysa Dorne", "sylth", "she/her", 26, "Street Bard", "velmora", None, "performer", (9,2,8,6,6,4,5,10), (8,14,10,16), {"dodging":25,"magic":15,"trading":20}, ["dagger_sunsilver"],
  "Plays the plaza fountain by day and the noble salons by night, collecting secrets as easily as coins.",
  "A new audience! Shall I play you something sad or something scandalous?", ["jewelry","herbs"], ["hide"], True, {"friendship":25}, {}),

 ("ruda", "Forewoman Ruda Kast", "kethari", "she/her", 44, "Mine Forewoman", "cinderdeep", "ironhold", "worker", (5,5,9,6,7,4,8,5), (24,9,24,10), {"mining":60,"melee":25}, ["hammer_greyvein"],
  "Runs the upper galleries with an iron voice. Lost her crew to a collapse in the Deep Galleries and wants the lower seams reopened safely.",
  "If you're here to gawk, gawk somewhere else. If you're here to dig, grab a pick.", ["ore","tools"], ["magic"], False,
  {"rep":{"ironhold":30}, "respect":40}, {}),
 ("pell", "Pell Underhill", "human", "he/him", 20, "Miner", "cinderdeep", "ironhold", "worker", (7,1,3,5,9,3,6,5), (13,10,12,9), {"mining":20}, [],
  "Sends every mark home to a sick mother in Saltmarket. Terrified of the dark, works in it anyway.",
  "H-hello. Are you from the guild? I've been working, I promise.", ["food","herbs"], ["weapons"], True, {"gold":60}, {}),
 ("grint", "Grint", "murrok", "he/him", 34, "Ex-raider Miner", "cinderdeep", None, "worker", (3,8,7,4,6,4,8,3), (22,11,24,8), {"unarmed":40,"mining":30,"melee":20}, ["knuckles_rustite"],
  "Left the Thornblood raiding bands after a raid went wrong. Digs rock now, because rock doesn't scream.",
  "You want something, talk. You want a fight, also fine.", ["food","hide"], ["jewelry"], False,
  {"respect":30, "favor":"grint_brawl", "favor_desc":"Beat him in a fistfight."}, {}),
 ("ottile", "Ottile Brune", "kethari", "she/her", 58, "Ore Assayer", "cinderdeep", "ironhold", "merchant", (4,2,7,9,4,9,5,4), (12,6,14,11), {"trading":55,"mining":25}, [],
  "Weighs every lump of ore that leaves Cinderdeep and takes a sliver of each. Very, very rich.",
  "Ore? Let's see it. Don't waste my scale with rubbish.", ["jewelry","ore"], ["food"], False, {"gold":400}, {"shop":"assayer"}),

 ("borun_kett", "Guildmaster Borun Kett", "kethari", "he/him", 61, "Guildmaster", "hammerlee", "ironhold", "noble", (5,4,9,8,6,7,8,5), (20,7,20,12), {"crafting":70,"trading":50}, ["hammer_sunsilver"],
  "Has run the Ironhold Guild for twenty years and intends to outlive both the Queen and her taxes.",
  "Every blade in this region passes through my guild eventually. What do you want?", ["ore","tools"], ["herbs"], False,
  {"rep":{"ironhold":80}, "respect":70, "friendship":50, "favor":"kett_succession", "favor_desc":"Secure the guild's future: deliver 20 Sunsilver bars and back his chosen successor."}, {"leader":True}),
 ("halvard", "Master Halvard Stone", "kethari", "he/him", 50, "Master Smith", "hammerlee", "ironhold", "merchant", (4,4,9,7,8,5,7,3), (24,7,20,15), {"crafting":75,"melee":30}, ["hammer_greyvein"],
  "The finest smith in Hammerlee, and he will tell you so. Has never forged Voidglass and is quietly obsessed with it.",
  "Don't touch the anvil. What are you buying?", ["ore","weapons"], ["herbs"], False,
  {"rep":{"ironhold":50}, "friendship":40, "favor":"halvard_voidglass", "favor_desc":"Bring him 3 Voidglass ore."}, {"shop":"smithy"}),
 ("nessa", "Nessa Coil", "human", "she/her", 31, "Tinkerer", "hammerlee", "ironhold", "worker", (8,3,7,9,7,4,6,8), (10,11,11,17), {"crafting":55,"ranged":30}, ["firelock_greyvein"],
  "Invented (she insists) the firelock. The guild thinks her contraptions are a fire hazard. They are.",
  "Careful, that one's loaded. Probably. What do you think of springs?", ["tools","ore"], ["herbs"], True,
  {"friendship":30, "favor":"nessa_powder", "favor_desc":"Bring her 5 Salt and 2 Sunsilver ore for her powder experiments."}, {}),
 ("jory", "Jory Lark", "human", "he/him", 17, "Apprentice Smith", "hammerlee", "ironhold", "worker", (7,2,2,5,8,2,8,6), (13,10,11,10), {"crafting":20}, [],
  "Halvard's apprentice. Burns himself every day, apologises every day.",
  "S-sorry, master's busy. Can I help? I can probably help.", ["weapons","food"], ["drink"], False, {"friendship":20}, {}),
 ("vell", "Vell Ambrose", "sylth", "they/them", 33, "Leatherworker", "hammerlee", None, "merchant", (5,2,8,8,6,6,4,6), (9,13,10,18), {"crafting":50,"trading":30}, ["dagger_sunsilver"],
  "Makes armor so fine the Queen's guard orders from them. Finds everyone else slightly vulgar.",
  "You'd look less dreadful in a fitted jerkin. I can help with that, for a price.", ["jewelry","hide"], ["ore"], True, {"gold":250}, {"shop":"workshop"}),

 ("sela_marrow", "Sela Marrow", "human", "she/her", 46, "Mistress of the Caravan League", "saltmarket", "caravans", "noble", (6,3,9,9,5,8,6,8), (10,10,12,13), {"trading":80,"dodging":20}, ["dagger_sunsilver"],
  "Built the Free Caravan League from three wagons and a debt. Believes every problem has a price.",
  "Merchant, mercenary or mark? Everyone in Saltmarket is one of the three.", ["jewelry","books"], ["hide"], False,
  {"rep":{"caravans":80}, "friendship":50, "respect":60, "favor":"marrow_succession", "favor_desc":"Make the roads safe (the Hollow defeated) and confirm her successor."}, {"leader":True}),
 ("odo", "Captain Odo Brine", "human", "he/him", 52, "Smuggler Captain", "saltmarket", "caravans", "night_owl", (6,5,8,6,3,8,4,8), (16,10,16,13), {"trading":40,"melee":30,"ranged":25}, ["firelock_rustite"],
  "Officially a merchant captain. Unofficially, nothing passes Wrecker's Cove without his say-so.",
  "Ahoy, landlubber. Looking for work that doesn't ask questions?", ["drink","jewelry"], ["books"], False, {"gold":300}, {}),
 ("fenna", "Fenna Kiln", "murrok", "she/her", 28, "Caravan Guard", "saltmarket", "caravans", "guard", (9,5,7,5,8,3,9,9), (19,12,22,11), {"melee":40,"blocking":30,"athletics":30}, ["spear_greyvein"],
  "Has walked every caravan road in the region and sings on all of them. Badly.",
  "Heya! You heading out? Roads are safer with company!", ["food","herbs"], ["books"], True, {"gold":120}, {}),
 ("isk", "Isk", "sylth", "he/him", 40, "Information Broker", "saltmarket", None, "night_owl", (4,3,7,9,2,8,3,6), (8,15,9,17), {"dodging":40,"trading":45,"ranged":20}, ["throwing_sunsilver"],
  "Sells secrets in the warehouse district. No one knows his real name, including, he claims, himself.",
  "Everything has a price. Even this conversation. Lucky for you, the first minute's free.", ["books","jewelry"], ["food"], False,
  {"gold":200, "favor":"isk_secret", "favor_desc":"Trade him a secret: bring a Relic Shard from the Sunken Abbey."}, {}),
 ("tamsin", "Tamsin Grael", "human", "she/her", 38, "Fishmonger", "saltmarket", "caravans", "merchant", (8,2,6,5,6,5,6,10), (12,10,13,11), {"trading":30,"gathering":25}, ["dagger_rustite"],
  "Sells the freshest fish and the stalest gossip in Saltmarket, and enjoys the second more.",
  "Fresh fish! Fresh news! Did you hear what happened at the docks?", ["food","jewelry"], ["magic"], False, {"friendship":30}, {"shop":"provisioner"}),

 ("ivo_thale", "Archmage Ivo Thale", "sylth", "he/him", 112, "Archmage", "glimmerfen", "ashen", "scholar", (5,2,8,10,7,3,6,3), (6,10,9,14), {"magic":90}, [],
  "Leader of the Ashen Circle for half a century. Believes the vanished builders destroyed themselves with unregulated magic.",
  "Ah. Another bright spark who thinks they understand mana. Sit.", ["magic","books"], ["weapons"], False,
  {"rep":{"ashen":80}, "friendship":50, "skill":{"magic":60}, "favor":"thale_spire", "favor_desc":"Recover the core relic of the Shattered Spire."}, {"leader":True}),
 ("mirela", "Mirela Vox", "sylth", "she/her", 37, "Spell Tutor", "glimmerfen", "ashen", "merchant", (3,4,8,9,7,5,6,3), (8,12,10,15), {"magic":65,"trading":30}, [],
  "Teaches spell construction to anyone who can pay and few who can keep up. Ruthlessly precise.",
  "Your mana flow is atrocious. Fortunately, I charge by the lesson.", ["magic","books"], ["drink"], True,
  {"rep":{"ashen":30}, "skill":{"magic":20}}, {"shop":"enchanter"}),
 ("hob", "Hob Mosswick", "human", "he/him", 55, "Bog Guide", "glimmerfen", None, "worker", (8,2,4,6,7,3,6,7), (13,11,15,12), {"gathering":45,"ranged":25}, ["spear_rustite"],
  "Knows every safe path through Mirelight Bog, and most of the unsafe ones.",
  "Mind the green water, friend. Green's fine. Glowing green - not fine.", ["drink","food"], ["books"], False, {"gold":80}, {}),
 ("anwen", "Sister Anwen", "human", "she/her", 30, "Circle Healer", "glimmerfen", "ashen", "worker", (10,1,5,7,9,1,8,6), (8,10,11,12), {"magic":40,"gathering":25}, [],
  "A healer who left the Crown temples to study light-magic medicine with the Ashen Circle.",
  "Be welcome. If you carry any wounds - any at all - come to me first.", ["herbs","books"], ["weapons"], True, {"friendship":40}, {}),

 ("kara", "Kara 'Ironjaw' Vosk", "kethari", "she/her", 42, "Mercenary Boss", "redwater", None, "noble", (4,7,9,6,5,7,6,5), (25,10,24,13), {"melee":60,"blocking":45}, ["battleaxe_greyvein"],
  "Runs the Redwater Company and the fighting pit. Earned her nickname by catching a mace with her teeth.",
  "You fight? You pay? Or you leave. Those are the options.", ["weapons","drink"], ["herbs"], False,
  {"respect":60, "gold":500, "favor_desc":"Earn her respect in the pit and buy out her company's contract."}, {}),
 ("rennick", "Rennick Shaw", "human", "he/him", 47, "Veteran Sellsword", "redwater", None, "guard", (4,5,7,6,6,6,5,4), (20,11,20,16), {"melee":55,"blocking":35,"ranged":20}, ["longsword_greyvein"],
  "Has fought for every faction in the region and been betrayed by most of them.",
  "Two hundred marks and I'll follow you into anything short of the Spire.", ["drink","weapons"], ["books"], False, {"gold":200}, {}),
 ("lio", "Lio Tamber", "murrok", "he/him", 23, "Pit Fighter", "redwater", None, "performer", (6,8,9,4,6,5,5,8), (23,15,21,12), {"unarmed":55,"dodging":35}, ["knuckles_greyvein"],
  "Undefeated champion of the Redwater pit for two seasons. Very loud about it.",
  "You've heard of me. Everyone's heard of me. Want an autograph or a beating?", ["food","jewelry"], ["books"], True,
  {"respect":35, "favor":"lio_pit", "favor_desc":"Beat him in the fighting pit."}, {}),
 ("della", "Della Crane", "human", "she/her", 35, "Bounty Clerk", "redwater", None, "merchant", (6,3,7,8,8,4,7,6), (10,10,12,14), {"trading":35,"ranged":30}, ["crossbow_rustite"],
  "Keeps the bounty ledger and pays out fairly, which in Redwater makes her a saint.",
  "Bounties on the board, pay on proof. No proof, no pay.", ["books","drink"], ["hide"], False, {"friendship":35}, {}),
 ("shade", "Yeva 'Shade'", "sylth", "she/her", 29, "Mercenary Archer", "redwater", None, "night_owl", (3,5,8,7,6,5,7,2), (10,16,11,20), {"ranged":60,"dodging":40}, ["bow_sunsilver"],
  "A silent archer who only takes contracts against bandits. Doesn't say why.",
  "...", ["weapons","herbs"], ["drink"], True, {"gold":250}, {}),

 ("gruka", "Warchief Gruka", "murrok", "he/him", 55, "Warchief", "thornhollow", "thornblood", "noble", (4,7,9,6,7,3,9,5), (28,10,28,10), {"melee":65,"unarmed":50}, ["battleaxe_sunsilver"],
  "Led the clans through the last war with the Crown and has kept an uneasy peace since. Will not bow.",
  "An outsider in Thornhollow. Speak, and speak true.", ["hide","weapons"], ["jewelry"], False,
  {"rep":{"thornblood":80}, "respect":70, "friendship":40, "favor":"gruka_peace", "favor_desc":"Broker a lasting peace between the clans and the Crown."}, {"leader":True}),
 ("ama", "Ama Thornsinger", "murrok", "she/her", 64, "Shaman", "thornhollow", "thornblood", "elder", (7,2,7,8,8,2,8,5), (14,8,18,10), {"magic":50,"gathering":40}, [],
  "Speaks to the forest and the clan listens. Believes the Ashfall Crater is waking up.",
  "The trees told me someone was coming. They did not say you'd be so small.", ["herbs","magic"], ["ore"], False,
  {"rep":{"thornblood":30}, "friendship":30}, {}),
 ("brakka", "Brakka", "murrok", "she/her", 31, "Hunter", "thornhollow", "thornblood", "worker", (4,6,8,6,8,3,7,3), (21,15,21,15), {"ranged":45,"gathering":40,"melee":25}, ["bow_greyvein"],
  "The clan's best tracker. Judges people by whether they can keep up.",
  "You walk loud. Like a cart.", ["hide","weapons"], ["drink"], True,
  {"respect":40, "favor":"brakka_hunt", "favor_desc":"Complete the hunting trial in the Thornwild."}, {}),
 ("tashi", "Tashi Burrfoot", "murrok", "he/him", 20, "Young Trader", "thornhollow", "thornblood", "merchant", (9,2,5,6,8,4,6,9), (14,12,15,11), {"trading":30,"gathering":20}, ["throwing_rustite"],
  "The first murrok in generations to trade openly with the Crown towns. Endlessly curious about the west.",
  "A traveler! Is it true that in Velmora the houses are made entirely of stone?", ["jewelry","books"], ["weapons"], True, {"friendship":20}, {"shop":"tannery"}),

 ("elise", "Warden Elise Harrow", "human", "she/her", 40, "Frontier Warden", "duskreach", "crown", "guard", (4,5,8,7,9,2,9,3), (19,13,19,15), {"melee":45,"ranged":40}, ["crossbow_greyvein"],
  "Commands twelve tired soldiers at the edge of the map. Has written to Velmora for reinforcements nine times.",
  "Duskreach is open. The east isn't. Don't go past the tower after dark.", ["weapons","food"], ["drink"], True,
  {"rep":{"crown":20}, "respect":30}, {}),
 ("mott", "Mott Grimsby", "human", "he/him", 50, "Scavenger Dealer", "duskreach", None, "merchant", (5,2,6,6,3,9,3,6), (11,8,13,12), {"trading":45}, ["dagger_rustite"],
  "Buys what scavengers drag back from the east and sells it at four times the price. Asks no questions.",
  "Relics, scrap, oddities. Buying and selling. Mostly buying cheap.", ["jewelry","relic"], ["books"], False, {"gold":150}, {"shop":"scavenger_shop"}),
 ("kethra", "Kethra Dunmore", "kethari", "she/her", 27, "Ruin Delver", "duskreach", None, "wanderer", (8,4,9,7,7,5,6,7), (18,12,19,14), {"mining":35,"melee":30,"dodging":25}, ["polearm_greyvein"],
  "Has been inside the Shattered Spire twice and came back both times, which makes her the region's leading expert.",
  "Planning to go east? Good. I need someone mad enough to come with me.", ["relic","ore"], ["herbs"], True, {"friendship":30}, {}),
 ("aubric", "Father Aubric", "human", "he/him", 63, "Hermit Priest", "duskreach", None, "elder", (8,1,4,8,9,1,7,4), (9,7,12,10), {"magic":35,"gathering":20}, ["mace_rustite"],
  "Tends the frontier chapel and buries what the husks leave behind. Something in the Spire took his brother.",
  "Light keep you, traveler. You've come a long way to the edge of things.", ["herbs","books"], ["drink"], False,
  {"friendship":40, "favor":"aubric_husks", "favor_desc":"Clear the husks from Duskmoor's standing stones."}, {}),

 ("ysolde", "Ysolde Frost", "human", "she/her", 34, "Lone Hunter", "frostfang_ridge", None, "wanderer", (3,5,8,7,8,3,7,1), (18,14,19,18), {"ranged":55,"gathering":45}, ["bow_greyvein"],
  "Lives alone on the ridge, hunting ice wolves and mapping Sunsilver veins nobody else can reach.",
  "You'll freeze in that. Sit by the fire before you say anything.", ["hide","food"], ["jewelry"], True,
  {"friendship":35, "favor":"ysolde_hides", "favor_desc":"Bring her 4 Raw Hides so she can make it through winter."}, {}),
 ("margit", "Margit", "human", "she/her", 77, "Bog Witch", "mirelight_bog", None, "hermit", (5,3,8,9,6,5,5,2), (7,7,12,11), {"magic":55,"gathering":60}, [],
  "Expelled from the Ashen Circle forty years ago for 'unsanctioned experimentation'. Still experimenting.",
  "Visitors! How rare. Do try not to step on the toads; some of them used to be people.", ["herbs","magic"], ["weapons"], False,
  {"friendship":40, "favor":"margit_crystals", "favor_desc":"Bring her 3 Mana Crystals."}, {}),
 ("corin", "Sir Corin Vale", "human", "he/him", 32, "Wandering Knight", "widows_crossing", None, "wanderer", (7,4,6,6,10,1,10,5), (20,12,20,14), {"melee":50,"blocking":50}, ["longsword_greyvein"],
  "A knight without a lord, sworn to protect Widow's Crossing until it is lived in again.",
  "Hail, traveler. These roads need guarding, and I am the one guarding them.", ["weapons","food"], ["drink"], True,
  {"respect":30, "favor":"corin_settle", "favor_desc":"Bring people back to Widow's Crossing: found an outpost there."}, {}),
 ("nix", "Nix", "sylth", "they/them", 22, "Captive Thief", "redrock_canyon", None, "wanderer", (6,4,6,8,4,6,6,6), (9,17,10,18), {"dodging":45,"melee":25}, ["dagger_greyvein"],
  "A thief who stole from the Hollow and got caught. Currently in a cage, currently very polite.",
  "Hey! Hey, you! Get me out of here and I swear I'll make it worth your while.", ["jewelry","food"], ["books"], True,
  {"favor":"nix_rescue", "favor_desc":"Free Nix from the Hollow's cage in Redrock Canyon."}, {}),
 ("black_ren", "Black Ren", "human", "he/him", 44, "Chief of the Hollow", "hollow_fort", "hollow", "night_owl", (3,8,9,8,4,8,5,5), (22,14,22,18), {"melee":65,"dodging":45}, ["longsword_sunsilver"],
  "A former Crown officer who turned outlaw after Velmora hanged his men for a defeat that wasn't theirs. Runs the Hollow like an army.",
  "You walked into my fort. Either you're very brave or very lost.", ["weapons","drink"], ["books"], False,
  {"favor":"ren_spared", "favor_desc":"Defeat Black Ren in combat and spare his life.", "alt":{"rep":{"hollow":50}, "respect":50}}, {"leader":True}),
]


def build():
    out = []
    for r in ROWS:
        (nid, name, race, pron, age, occ, home, fac, sched, pers, attrs, skills, equip,
         bg, greet, likes, dislikes, romance, recruit, extra) = r
        npc = {
            "id": nid, "name": name, "race": race, "pronouns": pron, "age": age,
            "occupation": occ, "home": home, "faction": fac, "schedule": sched,
            "personality": dict(zip(P, pers)), "attributes": dict(zip(A, attrs)),
            "skills": skills, "equipment": equip, "background": bg, "greeting": greet,
            "likes": likes, "dislikes": dislikes, "romanceable": romance, "recruit": recruit,
        }
        npc.update(extra)
        out.append(npc)
    return out


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "data", "npcs.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(build(), f, indent=1)
    print(f"wrote {len(ROWS)} NPCs -> {os.path.normpath(path)}")
