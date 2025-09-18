"""
Pattern Detector - Identifica padrões em conversas
Detecta sequências, repetições e comportamentos
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import Counter
import re

from utils.logger import get_logger

logger = get_logger(__name__)

class PatternType:
    """Tipos de padrões detectáveis"""
    RECURRING_QUESTION = "recurring_question"
    DAILY_ROUTINE = "daily_routine"
    TOPIC_SEQUENCE = "topic_sequence"
    ERROR_RECOVERY = "error_recovery"
    SATISFACTION_SIGNAL = "satisfaction_signal"
    CONVERSATION_FLOW = "conversation_flow"
    COMMAND_PATTERN = "command_pattern"

class PatternDetector:
    """
    Detecta e analisa padrões em conversas
    """
    
    def __init__(self):
        # Thresholds de detecção
        self.min_similarity = 0.7
        self.min_pattern_occurrences = 2
        self.time_window_hours = 168  # 1 semana
        
        # Cache de padrões detectados
        self.pattern_cache: Dict[str, List[Dict]] = {}
        
        logger.info("📊 Pattern Detector initialized")
    
    async def detect_patterns(self,
                             user_id: str,
                             current_message: str,
                             conversation_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detecta todos os padrões relevantes na conversa
        """
        patterns = []
        
        # 1. Detectar perguntas recorrentes
        recurring = await self._detect_recurring_questions(
            current_message, conversation_history
        )
        if recurring:
            patterns.extend(recurring)
        
        # 2. Detectar rotinas diárias
        routine = await self._detect_daily_routines(
            user_id, conversation_history
        )
        if routine:
            patterns.append(routine)
        
        # 3. Detectar sequências de tópicos
        sequences = await self._detect_topic_sequences(
            conversation_history
        )
        if sequences:
            patterns.extend(sequences)
        
        # 4. Detectar sinais de satisfação/insatisfação
        satisfaction = await self._detect_satisfaction_patterns(
            current_message
        )
        if satisfaction:
            patterns.append(satisfaction)
        
        # 5. Detectar padrões de comando
        commands = await self._detect_command_patterns(
            current_message
        )
        if commands:
            patterns.extend(commands)
        
        # Adicionar metadata
        for pattern in patterns:
            pattern["detected_at"] = datetime.now().isoformat()
            pattern["user_id"] = user_id
        
        # Atualizar cache
        if user_id not in self.pattern_cache:
            self.pattern_cache[user_id] = []
        self.pattern_cache[user_id].extend(patterns)
        
        # Limitar cache
        if len(self.pattern_cache[user_id]) > 100:
            self.pattern_cache[user_id] = self.pattern_cache[user_id][-100:]
        
        logger.debug(f"Detected {len(patterns)} patterns for user {user_id}")
        
        return patterns
    
    async def _detect_recurring_questions(self,
                                         current_message: str,
                                         history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detecta perguntas que se repetem
        """
        patterns = []
        
        if not history:
            return patterns
        
        # Normalizar mensagem atual
        current_normalized = self._normalize_message(current_message)
        
        # Contar mensagens similares
        similar_messages = []
        for item in history:
            hist_message = item.get("message", "")
            if hist_message:
                similarity = self._calculate_similarity(
                    current_normalized,
                    self._normalize_message(hist_message)
                )
                
                if similarity >= self.min_similarity:
                    similar_messages.append({
                        "message": hist_message,
                        "timestamp": item.get("timestamp"),
                        "similarity": similarity
                    })
        
        # Se encontrou repetições
        if len(similar_messages) >= self.min_pattern_occurrences:
            patterns.append({
                "pattern_type": PatternType.RECURRING_QUESTION,
                "description": "Pergunta recorrente detectada",
                "occurrences": len(similar_messages),
                "confidence": min(0.9, len(similar_messages) * 0.2),
                "examples": similar_messages[:3],
                "suggestion": "Considerar criar resposta padrão ou FAQ"
            })
        
        return patterns
    
    async def _detect_daily_routines(self,
                                    user_id: str,
                                    history: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Detecta rotinas baseadas em horário
        """
        if not history:
            return None
        
        # Agrupar mensagens por hora do dia
        hourly_messages = Counter()
        
        for item in history:
            timestamp_str = item.get("timestamp")
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    hour = timestamp.hour
                    hourly_messages[hour] += 1
                except:
                    continue
        
        # Encontrar horário mais comum
        if hourly_messages:
            peak_hour, count = hourly_messages.most_common(1)[0]
            
            if count >= 3:  # Mínimo 3 ocorrências
                time_period = self._get_time_period(peak_hour)
                
                return {
                    "pattern_type": PatternType.DAILY_ROUTINE,
                    "description": f"Rotina de {time_period} detectada",
                    "peak_hour": peak_hour,
                    "occurrences": count,
                    "confidence": min(0.8, count * 0.15),
                    "time_period": time_period,
                    "suggestion": f"Preparar respostas otimizadas para {time_period}"
                }
        
        return None
    
    async def _detect_topic_sequences(self,
                                     history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detecta sequências comuns de tópicos
        """
        patterns = []
        
        if len(history) < 3:
            return patterns
        
        # Extrair sequências de tópicos
        topics = []
        for item in history[-10:]:  # Últimas 10 mensagens
            topic = self._extract_topic(item.get("message", ""))
            if topic:
                topics.append(topic)
        
        # Identificar sequências que se repetem
        sequences = self._find_sequences(topics)
        
        for seq, count in sequences.items():
            if count >= 2:
                patterns.append({
                    "pattern_type": PatternType.TOPIC_SEQUENCE,
                    "description": f"Sequência de tópicos: {' -> '.join(seq)}",
                    "sequence": seq,
                    "occurrences": count,
                    "confidence": min(0.7, count * 0.25),
                    "suggestion": "Antecipar próximo tópico na sequência"
                })
        
        return patterns
    
    async def _detect_satisfaction_patterns(self,
                                           message: str) -> Optional[Dict[str, Any]]:
        """
        Detecta sinais de satisfação ou insatisfação
        """
        # Indicadores
        positive_indicators = [
            "obrigado", "valeu", "perfeito", "ótimo", "excelente",
            "muito bom", "ajudou", "resolveu", "funcionou", "top"
        ]
        
        negative_indicators = [
            "não entendi", "errado", "incorreto", "não é isso",
            "péssimo", "ruim", "não funcionou", "problema continua",
            "não ajudou", "confuso"
        ]
        
        message_lower = message.lower()
        
        # Contar indicadores
        positive_count = sum(1 for ind in positive_indicators if ind in message_lower)
        negative_count = sum(1 for ind in negative_indicators if ind in message_lower)
        
        if positive_count > 0 or negative_count > 0:
            sentiment = "positive" if positive_count > negative_count else "negative"
            score = positive_count - negative_count
            
            return {
                "pattern_type": PatternType.SATISFACTION_SIGNAL,
                "description": f"Sinal de {'satisfação' if sentiment == 'positive' else 'insatisfação'} detectado",
                "sentiment": sentiment,
                "score": score,
                "confidence": min(0.9, abs(score) * 0.3),
                "positive_signals": positive_count,
                "negative_signals": negative_count,
                "suggestion": "Ajustar abordagem baseado no feedback" if sentiment == "negative" else "Manter abordagem atual"
            }
        
        return None
    
    async def _detect_command_patterns(self,
                                      message: str) -> List[Dict[str, Any]]:
        """
        Detecta padrões de comando ou solicitação
        """
        patterns = []
        
        # Padrões de comando comuns
        command_patterns = {
            "report_request": r"(gerar?|criar?|fazer?|montar?).*(relatório|report|dashboard)",
            "data_query": r"(buscar?|procurar?|encontrar?|listar?).*(dados?|informaç|registros?)",
            "help_request": r"(ajuda|help|socorro|dúvida|como|tutorial)",
            "status_check": r"(status|situação|andamento|progresso)",
            "calculation": r"(calcular?|somar?|média|total|quanto)",
            "comparison": r"(comparar?|diferença|versus|melhor|pior)"
        }
        
        message_lower = message.lower()
        
        for command_type, pattern in command_patterns.items():
            if re.search(pattern, message_lower):
                patterns.append({
                    "pattern_type": PatternType.COMMAND_PATTERN,
                    "description": f"Comando detectado: {command_type}",
                    "command_type": command_type,
                    "confidence": 0.8,
                    "matched_pattern": pattern,
                    "suggestion": f"Executar ação específica para {command_type}"
                })
        
        return patterns
    
    def _normalize_message(self, message: str) -> str:
        """
        Normaliza mensagem para comparação
        """
        if not message:
            return ""
        
        # Lowercase
        normalized = message.lower()
        
        # Remover pontuação
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        
        # Remover espaços extras
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calcula similaridade entre dois textos (Jaccard)
        """
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _get_time_period(self, hour: int) -> str:
        """
        Retorna período do dia baseado na hora
        """
        if 5 <= hour < 12:
            return "manhã"
        elif 12 <= hour < 18:
            return "tarde"
        elif 18 <= hour < 22:
            return "noite"
        else:
            return "madrugada"
    
    def _extract_topic(self, message: str) -> Optional[str]:
        """
        Extrai tópico principal da mensagem
        """
        if not message:
            return None
        
        # Mapeamento simples de palavras-chave para tópicos
        topic_keywords = {
            "finance": ["financeiro", "orçamento", "custo", "receita", "faturamento"],
            "report": ["relatório", "report", "dashboard", "análise"],
            "help": ["ajuda", "dúvida", "como", "tutorial"],
            "data": ["dados", "informação", "buscar", "consultar"],
            "status": ["status", "situação", "andamento"],
            "greeting": ["olá", "oi", "bom dia", "boa tarde", "boa noite"]
        }
        
        message_lower = message.lower()
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                return topic
        
        return "general"
    
    def _find_sequences(self, topics: List[str]) -> Dict[Tuple[str, ...], int]:
        """
        Encontra sequências que se repetem
        """
        sequences = Counter()
        
        # Buscar sequências de tamanho 2 e 3
        for seq_len in [2, 3]:
            for i in range(len(topics) - seq_len + 1):
                seq = tuple(topics[i:i + seq_len])
                sequences[seq] += 1
        
        # Filtrar sequências com mais de uma ocorrência
        return {seq: count for seq, count in sequences.items() if count > 1}
    
    async def get_pattern_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Retorna resumo dos padrões detectados para um usuário
        """
        if user_id not in self.pattern_cache:
            return {
                "user_id": user_id,
                "total_patterns": 0,
                "pattern_types": {},
                "last_detection": None
            }
        
        patterns = self.pattern_cache[user_id]
        
        # Agrupar por tipo
        pattern_types = Counter(p["pattern_type"] for p in patterns)
        
        # Última detecção
        last_detection = max(
            (p.get("detected_at") for p in patterns),
            default=None
        )
        
        return {
            "user_id": user_id,
            "total_patterns": len(patterns),
            "pattern_types": dict(pattern_types),
            "last_detection": last_detection,
            "top_patterns": patterns[-5:]  # Últimos 5 padrões
        }