from typing import List, Dict
from dataclasses import dataclass
from core_progress.search_similar_question import match_byString_fromDB_forGraph
from db.db_manager import DatabaseManager

@dataclass
class Question:
    """问题节点"""
    id: str
    content: str
    table_id: str
    layer: int = 0

@dataclass 
class SimilarityResult:
    """相似度结果"""
    table_id: str
    similarity_score: float

class SimilarityGraphBuilder:
    """简化的相似度图构建器"""
    
    def __init__(self, max_layers: int = 2, top_n: int = 5):
        self.max_layers = max_layers
        self.top_n = top_n
        self.nodes = {}  # {question_id: Question}
        self.edges = []  # [{'source': id, 'target': id, 'similarity_score': float}]
        self.table_to_question = {}  # {table_id: question_id} 映射表
        self.db_manager = DatabaseManager()
            # 新增：记录第二层节点的父节点关系
        self.layer2_parent_mapping = {}  # {layer2_node_id: layer1_parent_id}
 
    def get_question_by_table_id(self, table_id: str) -> str:
        """根据table_id获取对应的question内容"""
        try:
            knowledge_record = self.db_manager.get_knowledge_by_id(table_id)
            return knowledge_record.get("question", "") if knowledge_record else ""
        except Exception:
            return ""
    
    def search_similar_questions(self, question_content: str) -> List[SimilarityResult]:
        """使用字符串匹配搜索相似问题"""
        try:
            if not question_content:
                return []
            
            _, similar_results = match_byString_fromDB_forGraph(question_content, self.top_n+1)
            
            return [
                SimilarityResult(
                    table_id=item['table_id'],
                    similarity_score=item['similarity_byString']
                )
                for item in similar_results[1:]
            ]
            
        except Exception:
            return []
    
    def create_question_node(self, table_id: str, question_content: str, layer: int) -> Question:
        """创建问题节点"""
        if not question_content:
            question_content = self.get_question_by_table_id(table_id)
        
        return Question(
            id=table_id,
            content=question_content,
            table_id=table_id,
            layer=layer
        )
    
    def edge_exists(self, source_id: str, target_id: str) -> bool:
        """检查边是否已存在"""
        return any(
            edge['source'] == source_id and edge['target'] == target_id 
            for edge in self.edges
        )
    
    def add_edge(self, source_id: str, target_id: str, similarity_score: float):
        """添加边（避免重复）"""
        if not self.edge_exists(source_id, target_id):
            self.edges.append({
                'source': source_id,
                'target': target_id,
                'similarity_score': similarity_score,
            })
    
    def build_graph(self, start_question_content: str, start_table_id: str = None) -> Dict:
        """构建简化的相似度图"""
        try:
            # 初始化起始节点
            start_table_id = start_table_id or "user_query"
            start_question = self.create_question_node(start_table_id, start_question_content, layer=0)
            self.nodes[start_question.id] = start_question
            self.table_to_question[start_table_id] = start_question.id
            
            # 第1层扩展
            layer1_results = self.search_similar_questions(start_question_content)
            layer1_questions = []
            
            for result in layer1_results:
                if result.table_id in self.table_to_question:
                    # 节点已存在，添加边到现有节点
                    existing_node_id = self.table_to_question[result.table_id]
                    self.add_edge(start_question.id, existing_node_id, result.similarity_score)
                else:
                    # 创建新的第1层问题节点
                    layer1_question = self.create_question_node(result.table_id, "", layer=1)
                    self.nodes[layer1_question.id] = layer1_question
                    self.table_to_question[result.table_id] = layer1_question.id
                    layer1_questions.append(layer1_question)
                    self.add_edge(start_question.id, layer1_question.id, result.similarity_score)
            
            # 第2层扩展
            if self.max_layers >= 2 and layer1_questions:
                for q in layer1_questions:
                    # 确保问题内容存在
                    if not q.content:
                        q.content = self.get_question_by_table_id(q.table_id)
                        self.nodes[q.id] = q
                    
                    # 搜索第2层相似问题
                    layer2_results = self.search_similar_questions(q.content)
                    
                    for result in layer2_results:
                        # 避免自循环
                        if result.table_id == q.table_id:
                            continue
                        
                        # 检查节点是否已存在
                        if result.table_id in self.table_to_question:
                            target_question_id = self.table_to_question[result.table_id]
                        else:
                            # 创建新的第2层节点
                            layer2_question = self.create_question_node(result.table_id, "", layer=2)
                            self.nodes[layer2_question.id] = layer2_question
                            self.table_to_question[result.table_id] = layer2_question.id
                            target_question_id = layer2_question.id
                            # 记录第二层节点的父节点关系
                            self.layer2_parent_mapping[target_question_id] = q.id
                        
                        # 添加第2层边
                        self.add_edge(q.id, target_question_id, result.similarity_score)
            
            return self.to_dict()
            
        except Exception:
            return {'nodes': [], 'edges': []}
    
    def to_dict(self) -> Dict:
        """转换为图数据字典"""
        return {
            'nodes': [
                {
                    'id': node.id,
                    'content': node.content,
                    'table_id': node.table_id,
                    'layer': node.layer
                }
                for node in self.nodes.values()
            ],
            'links': [
                {
                    'source': edge['source'],
                    'target': edge['target'],
                    'similarity_score': edge['similarity_score']
                }
                for edge in self.edges
            ]
        }
    
    def to_echarts_format(self) -> Dict:
        """转换为ECharts需要的格式"""
        # 定义节点颜色组，使用高对比度、差异明显的颜色
        distinct_colors = [
            "#FF3E30",  # 鲜红色
            "#1E88E5",  # 蓝色
            "#FFC107",  # 金黄色
            "#43A047",  # 绿色
            "#9C27B0",  # 紫色
            "#00BCD4",  # 青色
            "#FF9800",  # 橙色
            "#795548",  # 棕色
            "#607D8B",  # 蓝灰色
            "#E91E63",  # 粉色
            "#673AB7",  # 深紫色
            "#3F51B5",  # 靛蓝色
            "#009688",  # 蓝绿色
            "#CDDC39",  # 酸橙色
            "#FFEB3B",  # 黄色
        ]
        
        # 为第一层节点分配颜色索引
        layer1_nodes = [node for node in self.nodes.values() if node.layer == 1]
        layer1_color_mapping = {}
        for i, node in enumerate(layer1_nodes):
            layer1_color_mapping[node.id] = i % len(distinct_colors)
        
        # 定义层级类别
        categories = [
            {"name": "起始问题", "itemStyle": {"color":"rgba(0, 0, 0, 0.8)"}},  # 黑色，更加突出
        ]
        
        # 为每个第一层节点创建单独的类别
        for i, (layer1_id, color_index) in enumerate(layer1_color_mapping.items()):
            layer1_node = self.nodes[layer1_id]
            categories.append({
                "name": f"问题组-{i+1}",
                "itemStyle": {"color": distinct_colors[color_index]}
            })
        
        # 为第二层节点准备略浅色版本的颜色
        layer2_category_offset = len(categories)
        for i, (layer1_id, color_index) in enumerate(layer1_color_mapping.items()):
            # 为每个第一层节点的子节点创建略淡的颜色
            original_color = distinct_colors[color_index]
            categories.append({
                "name": f"子问题组-{i+1}",
                "itemStyle": {"color": original_color, "opacity": 0.5}  # 使用相同颜色但透明度降低
            })
        
        line_width_levels = [11, 8, 6, 4, 2, 1]  # 线条宽度级别
        
        # 以下代码保持不变
        source_edges = {}
        for edge in self.edges:
            source_id = edge['source']
            if source_id not in source_edges:
                source_edges[source_id] = []
            source_edges[source_id].append(edge)
        
        all_edge_widths = {}
        for source_id, edges_group in source_edges.items():
            # 按相似度降序排序
            sorted_edges = sorted(edges_group, key=lambda x: x['similarity_score'], reverse=True)
            
            for i, edge in enumerate(sorted_edges):
                level_index = min(i, 4)  # 最多5个级别
                width = line_width_levels[level_index]
                edge_key = f"{edge['source']}-{edge['target']}"
                all_edge_widths[edge_key] = width
        
        # 转换节点格式
        nodes = []
        for node in self.nodes.values():
            # 根据层级设置节点大小
            node_size = 50 if node.layer == 0 else (40 if node.layer == 1 else 25)
            
            # 确定节点类别
            if node.layer == 0:
                category = 0  # 起始问题
            elif node.layer == 1:
                # 第一层节点直接使用其颜色索引+1作为类别
                # +1是因为类别0被起始节点占用
                category = layer1_color_mapping.get(node.id, 0) + 1
            else:  # layer == 2
                # 根据父节点确定类别
                parent_id = self.layer2_parent_mapping.get(node.id)
                if parent_id and parent_id in layer1_color_mapping:
                    category = layer2_category_offset + layer1_color_mapping[parent_id]
                else:
                    category = 1  # 默认使用第一个颜色类别
            
            nodes.append({
                'id': node.id,
                'name': node.content,
                'symbolSize': node_size,
                'category': category,
            })
        
        # 转换边格式
        links = []
        for edge in self.edges:
            edge_key = f"{edge['source']}-{edge['target']}"
            line_width = all_edge_widths.get(edge_key, 3)
            line_opacity = max(0.5, min(1.0, edge['similarity_score'] + 0.2))  # 提高最小透明度
            similarity_value = round(edge['similarity_score'], 2)
            
            links.append({
                'source': edge['source'],
                'target': edge['target'],
                'value': similarity_value,
                'lineStyle': {
                    'width': line_width,
                    'opacity': line_opacity,
                    'curveness': 0.2
                },
            })
        
        return {
            'nodes': nodes,
            'links': links,
            'categories': categories
        }