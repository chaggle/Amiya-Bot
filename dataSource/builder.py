import re

from core.util.common import remove_xml_tag, integer

from .unitConfig import Config
from .sourceBank import SourceBank

attr_dict = {
    'maxHp': '最大生命值',
    'atk': '攻击力',
    'def': '防御力',
    'magicResistance': '魔法抗性',
    'cost': '部署费用',
    'blockCnt': '阻挡数',
    'baseAttackTime': '攻击间隔',
    'respawnTime': '再部署时间'
}


def parse_template(blackboard, description):
    formatter = {
        '0%': lambda v: f'{round(v * 100)}%'
    }
    data_dict = {item['key']: item['value'] for index, item in enumerate(blackboard)}
    desc = remove_xml_tag(description)
    format_str = re.findall(r'({(\S+?)})', desc)
    if format_str:
        for desc_item in format_str:
            key = desc_item[1].split(':')
            fd = key[0].lower().strip('-')
            if fd in data_dict:
                value = integer(data_dict[fd])

                if len(key) >= 2 and key[1] in formatter:
                    value = formatter[key[1]](value)

                desc = desc.replace(desc_item[0], str(value))

    return desc


class Operator:
    def __init__(self, parent: SourceBank, code, data, voice_list, skins_list, is_recruit=False):
        self.parent = parent

        sub_classes = parent.get_json_data('uniequip_table')['subProfDict']

        self.id = code
        self.name = data['name']
        self.en_name = data['appellation']
        self.wiki_name = data['name']
        self.rarity = data['rarity'] + 1
        self.classes = Config.classes[data['profession']]
        self.classes_sub = sub_classes[data['subProfessionId']]['subProfessionName']
        self.classes_code = list(Config.classes.keys()).index(data['profession']) + 1
        self.type = Config.types[data['position']]
        self.tags = data['tagList']

        self.limit = self.name in Config.limit
        self.unavailable = self.name in Config.unavailable

        self.is_recruit = is_recruit

        self.voice_list = voice_list
        self.skins_list = skins_list

        self.__tags()
        self.__extra()

        self.data = data

    def detail(self):
        items = self.parent.get_json_data('item_table')['items']

        token_id = 'p_' + self.id
        token = None
        if token_id in items:
            token = items[token_id]

        max_phases = self.data['phases'][-1]
        max_attr = max_phases['attributesKeyFrames'][-1]['data']

        trait = remove_xml_tag(self.data['description'])
        if self.data['trait']:
            max_trait = self.data['trait']['candidates'][-1]
            trait = parse_template(max_trait['blackboard'], max_trait['overrideDescripton'] or trait)

        detail = {
            'operator_trait': trait.replace('\\n', '\n'),
            'operator_usage': self.data['itemUsage'] or '',
            'operator_quote': self.data['itemDesc'] or '',
            'operator_token': token['description'] if token else '',
            'max_level': '%s-%s' % (len(self.data['phases']) - 1, max_phases['maxLevel'])
        }
        detail.update(max_attr)

        return detail, self.data['favorKeyFrames'][-1]['data']

    def talents(self):
        talents = []
        if self.data['talents']:
            for item in self.data['talents']:
                max_item = item['candidates'][-1]
                talents.append({
                    'talents_name': max_item['name'],
                    'talents_desc': remove_xml_tag(max_item['description'])
                })

        return talents

    def potential(self):
        potential = []
        if self.data['potentialRanks']:
            for index, item in enumerate(self.data['potentialRanks']):
                potential.append({
                    'potential_desc': item['description'],
                    'potential_rank': index + 1
                })

        return potential

    def evolve_costs(self):
        evolve_cost = []
        for index, phases in enumerate(self.data['phases']):
            if phases['evolveCost']:
                for item in phases['evolveCost']:
                    evolve_cost.append({
                        'evolve_level': index,
                        'use_material_id': item['id'],
                        'use_number': item['count']
                    })

        return evolve_cost

    def skills(self):
        skill_data = self.parent.get_json_data('skill_table')

        skills = []
        skills_id = []
        skills_desc = {}
        skills_cost = {}
        for index, item in enumerate(self.data['skills']):
            code = item['skillId']

            if code not in skill_data:
                continue

            detail = skill_data[code]
            icon = 'skill_icon_' + (detail['iconId'] or detail['skillId'])

            if bool(detail) is False:
                continue

            skills_id.append(code)

            if code not in skills_desc:
                skills_desc[code] = []
            if code not in skills_cost:
                skills_cost[code] = []

            for lev, desc in enumerate(detail['levels']):
                description = parse_template(desc['blackboard'], desc['description'])
                skills_desc[code].append({
                    'skill_level': lev + 1,
                    'skill_type': desc['skillType'],
                    'sp_type': desc['spData']['spType'],
                    'sp_init': desc['spData']['initSp'],
                    'sp_cost': desc['spData']['spCost'],
                    'duration': integer(desc['duration']),
                    'description': description.replace('\\n', '\n'),
                    'max_charge': desc['spData']['maxChargeTime']
                })

            for lev, cond in enumerate(item['levelUpCostCond']):
                if bool(cond['levelUpCost']) is False:
                    continue

                for idx, cost in enumerate(cond['levelUpCost']):
                    skills_cost[code].append({
                        'mastery_level': lev + 1,
                        'use_material_id': cost['id'],
                        'use_number': cost['count']
                    })

            skills.append({
                'skill_no': code,
                'skill_index': index + 1,
                'skill_name': detail['levels'][0]['name'],
                'skill_icon': icon
            })

        return skills, skills_id, skills_cost, skills_desc

    def building_skills(self):
        building_data = self.parent.get_json_data('building_data')
        building_skills = building_data['buffs']

        skills = []
        if self.id in building_data['chars']:
            char_buff = building_data['chars'][self.id]
            for buff in char_buff['buffChar']:
                for item in buff['buffData']:
                    buff_id = item['buffId']
                    if buff_id in building_skills:
                        skill = building_skills[buff_id]
                        skills.append({
                            'bs_unlocked': item['cond']['phase'],
                            'bs_name': skill['buffName'],
                            'bs_desc': remove_xml_tag(skill['description'])
                        })

        return skills

    def voices(self):
        voices = []
        for item in self.voice_list:
            voices.append({
                'voice_title': item['voiceTitle'],
                'voice_text': item['voiceText'],
                'voice_no': item['voiceAsset']
            })

        return voices

    def stories(self):
        stories_data = self.parent.get_json_data('handbook_info_table')['handbookDict']
        stories = []
        if self.id in stories_data:
            for item in stories_data[self.id]['storyTextAudio']:
                stories.append({
                    'story_title': item['storyTitle'],
                    'story_text': item['stories'][0]['storyText']
                })
        return stories

    def skins(self):
        skins = []
        for item in self.skins_list:
            if '@' not in item['skinId']:
                continue

            skin_key = item['avatarId'].split('#')
            skin_data = item['displaySkin']

            skin_image = f'{skin_key[0]}%23{skin_key[1]}'
            skin_type = 1

            skins.append({
                'skin_image': skin_image,
                'skin_type': skin_type,
                'skin_name': skin_data['skinName'] or self.name,
                'skin_drawer': skin_data['drawerName'] or '',
                'skin_group': skin_data['skinGroupName'] or '',
                'skin_content': skin_data['dialog'] or '',
                'skin_usage': skin_data['usage'] or '',
                'skin_desc': skin_data['description'] or '',
                'skin_source': skin_data['obtainApproach'] or ''
            })

        return skins

    def modules(self):
        equips = self.parent.get_json_data('uniequip_table')
        equips_battle = self.parent.get_json_data('battle_equip_table')

        equips_rel = equips['charEquip']
        modules_list = equips['equipDict']
        mission_list = equips['missionList']

        modules = []
        if self.id in equips_rel:
            for m_id in equips_rel[self.id]:
                module = modules_list[m_id]

                module['missions'] = []
                module['detail'] = equips_battle[m_id] if m_id in equips_battle else None

                for mission in module['missionList']:
                    module['missions'].append(mission_list[mission])

                modules.append(module)

        return modules

    def __tags(self):
        self.tags.append(self.classes)
        self.tags.append(self.type)
        if str(self.rarity) in Config.high_star:
            self.tags.append(Config.high_star[str(self.rarity)])

        if self.id in ['char_285_medic2', 'char_286_cast3', 'char_376_therex']:
            self.tags.append('支援机械')

    def __extra(self):
        if self.id == 'char_1001_amiya2':
            self.name = '阿米娅近卫'
            self.en_name = 'AmiyaGuard'
            self.wiki_name = '阿米娅(近卫)'