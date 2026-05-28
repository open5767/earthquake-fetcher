"""GADM 行政区划数据适配器

数据来源: GADM (gadm.org) — 全球行政区划边界
格式: GeoJSON FeatureCollection

中国数据:
  - 省级 (gadm41_CHN_1): 37 个
  - 市级 (gadm41_CHN_2): 368 个
  - 县级 (gadm41_CHN_3): 2,421 个

抗震设防属性基于 GB 18306-2015 省级参考值映射。
"""

import json
import logging
import math
from typing import Optional

import requests

from models.zone import ZoneRecord, PROVINCE_SEISMIC

logger = logging.getLogger(__name__)

GADM_BASE = "https://geodata.ucdavis.edu/gadm/gadm4.1/json"
REQUEST_TIMEOUT = 120


class GadmAdapter:
    """GADM 行政区域数据适配器"""

    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "SimDataFetcher/1.0"})
        self._timeout = timeout

    def fetch_china_provinces(self) -> list[ZoneRecord]:
        """获取中国省级行政区划 (GADM Level 1) + 抗震设防属性"""
        url = f"{GADM_BASE}/gadm41_CHN_1.json"
        logger.info("GADM 中国省级: %s", url)

        try:
            resp = self._session.get(url, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("GADM 下载失败: %s", e)
            return []

        records = []
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            name_en = props.get("NAME_1", "")
            gid = props.get("GID_1", "")

            name_cn = self._cn_name(name_en)

            seismic = PROVINCE_SEISMIC.get(name_en, {})
            if not seismic:
                for key in PROVINCE_SEISMIC:
                    if key in name_en or name_en in key:
                        seismic = PROVINCE_SEISMIC[key]
                        break

            geom = feat.get("geometry", {})
            center = self._centroid(geom)
            coords_json = self._simplify_geom(geom)

            if len(coords_json) < 50:
                continue

            records.append(ZoneRecord(
                zone_id=gid,
                name=name_cn,
                name_en=name_en,
                level="province",
                parent_id="CHN",
                longitude=round(center[0], 4),
                latitude=round(center[1], 4),
                coordinates_json=coords_json,
                seismic_pga=seismic.get("pga"),
                seismic_intensity=seismic.get("intensity", ""),
                seismic_desc=seismic.get("desc", ""),
                source="gadm",
                raw_data=props,
            ))

        # 台湾
        records += self._fetch_taiwan()

        logger.info("GADM 市级解析完成: %d 条 (含台湾)", len(records))
        return records

    def _fetch_taiwan(self) -> list[ZoneRecord]:
        """获取台湾区域数据 (GADM 独立文件)"""
        url = f"{GADM_BASE}/gadm41_TWN_0.json"
        try:
            resp = self._session.get(url, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning("GADM 台湾数据下载失败: %s", e)
            return []

        records = []
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            name_en = props.get("COUNTRY", props.get("NAME_0", "Taiwan"))
            gid = "TWN"

            seismic = PROVINCE_SEISMIC.get("Taiwan", {})
            geom = feat.get("geometry", {})
            center = self._centroid(geom)
            coords_json = self._simplify_geom(geom)

            records.append(ZoneRecord(
                zone_id=gid,
                name="台湾",
                name_en=name_en,
                level="province",
                parent_id="CHN",
                longitude=round(center[0], 4),
                latitude=round(center[1], 4),
                coordinates_json=coords_json,
                seismic_pga=seismic.get("pga"),
                seismic_intensity=seismic.get("intensity", ""),
                seismic_desc=seismic.get("desc", ""),
                source="gadm",
                raw_data=props,
            ))

        return records

    @staticmethod
    def _cn_name(name_en: str) -> str:
        """英文省名 → 中文"""
        mapping = {
            "Anhui": "安徽", "Beijing": "北京", "Chongqing": "重庆", "Fujian": "福建",
            "Gansu": "甘肃", "Guangdong": "广东", "Guangxi": "广西", "Guizhou": "贵州",
            "Hainan": "海南", "Hebei": "河北", "Heilongjiang": "黑龙江", "Henan": "河南",
            "Hubei": "湖北", "Hunan": "湖南", "Jiangsu": "江苏", "Jiangxi": "江西",
            "Jilin": "吉林", "Liaoning": "辽宁", "NeiMongol": "内蒙古", "NingxiaHui": "宁夏",
            "Qinghai": "青海", "Shaanxi": "陕西", "Shandong": "山东", "Shanghai": "上海",
            "Shanxi": "山西", "Sichuan": "四川", "Tianjin": "天津", "XinjiangUygur": "新疆",
            "Xizang": "西藏", "Yunnan": "云南", "Zhejiang": "浙江",
            "HongKong": "香港", "Macau": "澳门", "Taiwan": "台湾",
        }
        return mapping.get(name_en, name_en)

    @staticmethod
    def _city_name(name_en: str) -> str:
        """常见市级行政区英文→中文"""
        mapping = {
            "Shijiazhuang": "石家庄", "Tangshan": "唐山", "Qinhuangdao": "秦皇岛",
            "Handan": "邯郸", "Xingtai": "邢台", "Baoding": "保定", "Zhangjiakou": "张家口",
            "Chengde": "承德", "Cangzhou": "沧州", "Langfang": "廊坊", "Hengshui": "衡水",
            "Taiyuan": "太原", "Datong": "大同", "Yangquan": "阳泉", "Changzhi": "长治",
            "Jincheng": "晋城", "Shuozhou": "朔州", "Jinzhong": "晋中", "Yuncheng": "运城",
            "Xinzhou": "忻州", "Linfen": "临汾", "Lüliang": "吕梁",
            "Hohhot": "呼和浩特", "Baotou": "包头", "Wuhai": "乌海", "Chifeng": "赤峰",
            "Tongliao": "通辽", "Ordos": "鄂尔多斯", "Hulunbuir": "呼伦贝尔",
            "Shenyang": "沈阳", "Dalian": "大连", "Anshan": "鞍山", "Fushun": "抚顺",
            "Benxi": "本溪", "Dandong": "丹东", "Jinzhou": "锦州", "Yingkou": "营口",
            "Changchun": "长春", "Jilin": "吉林市", "Siping": "四平", "Liaoyuan": "辽源",
            "Harbin": "哈尔滨", "Qiqihar": "齐齐哈尔", "Jixi": "鸡西", "Hegang": "鹤岗",
            "Daqing": "大庆", "Jiamusi": "佳木斯", "Mudanjiang": "牡丹江",
            "Nanjing": "南京", "Wuxi": "无锡", "Xuzhou": "徐州", "Changzhou": "常州",
            "Suzhou": "苏州", "Nantong": "南通", "Lianyungang": "连云港", "Huai'an": "淮安",
            "Yancheng": "盐城", "Yangzhou": "扬州", "Zhenjiang": "镇江", "Taizhou": "泰州",
            "Hangzhou": "杭州", "Ningbo": "宁波", "Wenzhou": "温州", "Jiaxing": "嘉兴",
            "Huzhou": "湖州", "Shaoxing": "绍兴", "Jinhua": "金华", "Quzhou": "衢州",
            "Zhoushan": "舟山", "Lishui": "丽水",
            "Hefei": "合肥", "Wuhu": "芜湖", "Bengbu": "蚌埠", "Huainan": "淮南",
            "Ma'anshan": "马鞍山", "Huaibei": "淮北", "Anqing": "安庆", "Huangshan": "黄山",
            "Fuzhou": "福州", "Xiamen": "厦门", "Putian": "莆田", "Sanming": "三明",
            "Quanzhou": "泉州", "Zhangzhou": "漳州", "Nanping": "南平", "Longyan": "龙岩",
            "Nanchang": "南昌", "Jingdezhen": "景德镇", "Pingxiang": "萍乡", "Jiujiang": "九江",
            "Ganzhou": "赣州", "Ji'an": "吉安", "Yichun": "宜春", "Fuzhou ": "抚州",
            "Jinan": "济南", "Qingdao": "青岛", "Zibo": "淄博", "Zaozhuang": "枣庄",
            "Dongying": "东营", "Yantai": "烟台", "Weifang": "潍坊", "Jining": "济宁",
            "Tai'an": "泰安", "Weihai": "威海", "Rizhao": "日照", "Linyi": "临沂", "Dezhou": "德州",
            "Zhengzhou": "郑州", "Kaifeng": "开封", "Luoyang": "洛阳", "Pingdingshan": "平顶山",
            "Anyang": "安阳", "Xinxiang": "新乡", "Nanyang": "南阳", "Shangqiu": "商丘",
            "Wuhan": "武汉", "Huangshi": "黄石", "Shiyan": "十堰", "Yichang": "宜昌",
            "Xiangyang": "襄阳", "Ezhou": "鄂州", "Jingmen": "荆门", "Xiaogan": "孝感",
            "Jingzhou": "荆州", "Huanggang": "黄冈", "Xianning": "咸宁", "Enshi": "恩施",
            "Changsha": "长沙", "Zhuzhou": "株洲", "Xiangtan": "湘潭", "Hengyang": "衡阳",
            "Shaoyang": "邵阳", "Yueyang": "岳阳", "Changde": "常德", "Zhangjiajie": "张家界",
            "Yiyang": "益阳", "Chenzhou": "郴州", "Yongzhou": "永州", "Huaihua": "怀化",
            "Guangzhou": "广州", "Shenzhen": "深圳", "Zhuhai": "珠海", "Shantou": "汕头",
            "Foshan": "佛山", "Shaoguan": "韶关", "Zhanjiang": "湛江", "Zhaoqing": "肇庆",
            "Jiangmen": "江门", "Maoming": "茂名", "Huizhou": "惠州", "Meizhou": "梅州",
            "Dongguan": "东莞", "Zhongshan": "中山",
            "Nanning": "南宁", "Liuzhou": "柳州", "Guilin": "桂林", "Wuzhou": "梧州",
            "Beihai": "北海", "Yulin": "玉林", "Guigang": "贵港",
            "Haikou": "海口", "Sanya": "三亚", "Danzhou": "儋州",
            "Chengdu": "成都", "Mianyang": "绵阳", "Guangyuan": "广元", "Deyang": "德阳",
            "Yibin": "宜宾", "Nanchong": "南充", "Dazhou": "达州", "Luzhou": "泸州",
            "Zigong": "自贡", "Panzhihua": "攀枝花", "Suining": "遂宁", "Neijiang": "内江",
            "Leshan": "乐山", "Meishan": "眉山", "Ziyang": "资阳", "Liangshan": "凉山",
            "Garze": "甘孜", "Aba": "阿坝",
            "Guiyang": "贵阳", "Zunyi": "遵义", "Liupanshui": "六盘水", "Anshun": "安顺",
            "Kunming": "昆明", "Qujing": "曲靖", "Yuxi": "玉溪", "Baoshan": "保山",
            "Zhaotong": "昭通", "Lijiang": "丽江", "Pu'er": "普洱", "Lincang": "临沧",
            "Dali": "大理", "Dehong": "德宏", "Nujiang": "怒江", "Diqing": "迪庆",
            "Lhasa": "拉萨", "Qamdo": "昌都", "Nyingchi": "林芝", "Shannan": "山南",
            "Xigaze": "日喀则", "Nagqu": "那曲", "Ngari": "阿里",
            "Xi'an": "西安", "Tongchuan": "铜川", "Baoji": "宝鸡", "Xianyang": "咸阳",
            "Weinan": "渭南", "Yan'an": "延安", "Hanzhong": "汉中", "Yulin City": "榆林市",
            "Lanzhou": "兰州", "Jiayuguan": "嘉峪关", "Jinchang": "金昌", "Baiyin": "白银",
            "Tianshui": "天水", "Wuwei": "武威", "Zhangye": "张掖", "Pingliang": "平凉",
            "Jiuquan": "酒泉", "Qingyang": "庆阳", "Dingxi": "定西", "Longnan": "陇南",
            "Gannan": "甘南", "Linxia": "临夏",
            "Xining": "西宁", "Haidong": "海东", "Haibei": "海北", "Huangnan": "黄南",
            "Hainan ": "海南州", "Golog": "果洛", "Yushu": "玉树", "Haixi": "海西",
            "Yinchuan": "银川", "Shizuishan": "石嘴山", "Wuzhong": "吴忠", "Guyuan": "固原",
            "Urumqi": "乌鲁木齐", "Karamay": "克拉玛依", "Turpan": "吐鲁番", "Hami": "哈密",
            "Kashgar": "喀什", "Hotan": "和田", "Aksu": "阿克苏", "Kizilsu": "克孜勒苏",
            "Ili": "伊犁", "Tacheng": "塔城", "Altay": "阿勒泰", "Bayingolin": "巴音郭楞",
            "Changji": "昌吉", "Bortala": "博尔塔拉",
        }
        return mapping.get(name_en.strip(), name_en)

    @staticmethod
    def _centroid(geom: dict) -> tuple[float, float]:
        """计算几何中心的近似值"""
        if geom["type"] == "Polygon":
            coords = geom["coordinates"][0]
        elif geom["type"] == "MultiPolygon":
            coords = geom["coordinates"][0][0]
        else:
            return 0, 0
        if not coords:
            return 0, 0
        lons = [p[0] for p in coords]
        lats = [p[1] for p in coords]
        return sum(lons) / len(lons), sum(lats) / len(lats)

    @staticmethod
    def _simplify_geom(geom: dict, max_total_points: int = 3000) -> str:
        """简化几何为 JSON 字符串。每种几何类型保留足够点以保证可渲染。"""
        if geom["type"] == "Polygon":
            ring = geom["coordinates"][0]
            step = max(1, len(ring) // max_total_points)
            simplified = [[round(p[0], 5), round(p[1], 5)] for p in ring[::step]]
            return json.dumps({"type": "Polygon", "coordinates": [simplified]})
        elif geom["type"] == "MultiPolygon":
            all_coords = []
            # 按外环点数排序，取最大的几个多边形
            parts = []
            for poly in geom["coordinates"]:
                if poly and poly[0]:
                    parts.append((len(poly[0]), poly))
            parts.sort(key=lambda x: -x[0])

            remaining = max_total_points
            for _, poly in parts:
                if remaining <= 0:
                    break
                ring = poly[0]
                alloc = max(30, min(remaining, len(ring)))
                step = max(1, len(ring) // alloc)
                # 每个 polygon = [outer_ring], 即 [[coord_pairs]]
                simplified_ring = [[round(p[0], 5), round(p[1], 5)] for p in ring[::step]]
                all_coords.append([simplified_ring])
                remaining -= len(ring) // step
            return json.dumps({"type": "MultiPolygon", "coordinates": all_coords})
        return ""

    def close(self):
        self._session.close()
