from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
import os
from typing import Dict, Any, List, Optional

class DatabaseManager:
    """
    Database manager providing MongoDB connection and collection access
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        load_dotenv()
        DB_HOST = os.environ.get("DB_HOST")
        DB_PORT = int(os.environ.get("DB_PORT"))
        DB_USER = os.environ.get("DB_USER")
        DB_PASSWORD = os.environ.get("DB_PASSWORD")
        self.client = MongoClient(host=DB_HOST, port=DB_PORT)
        # , username=DB_USER, password=DB_PASSWORD
        self.db = self.client["TableSage"]
        
        # Initialize collections
        self.knowledge_db = self.db["MutiKnowledgeDataBase"]
        self.learning_records = self.db["LearningRecordsDataBase"]
        self.teaching_records = self.db["GuidanceRecordsDataBase"] 
        self.error_records = self.db["ErrorRecordsDataBase"]
        
        # User and Chat History collections
        self.users = self.db["Users"]
        self.chat_sessions = self.db["ChatSessions"]
        self.result_cache_col = self.db["ResultCache"]
        self.multi_turn_sessions = self.db["MultiTurnSessions"]
        
        self._ensure_text_index()
        
        self._initialized = True
    
    def _ensure_text_index(self):
        try:
            existing_indexes = self.knowledge_db.list_indexes()
            text_index_exists = False
            for idx in existing_indexes:
                if 'question_text' in idx.get('name', ''):
                    text_index_exists = True
                    break
                
            if not text_index_exists:
                self.knowledge_db.create_index([("question", "text")], name="question_text")
        except Exception as e:
            print(f"⚠️ Index check failed: {str(e)}")
    
    def get_knowledge_by_id(self, table_id):
        """
        Get knowledge entry by specified ID
        
        Args:
            table_id: Table ID
            
        Returns:
            dict: Knowledge entry record
        """
        return self.knowledge_db.find_one({"table_id": table_id})
        
    def get_learning_record(self, table_id):
        """
        Get learning record
        
        Args:
            table_id: Table ID
            
        Returns:
            dict: Learning record
        """
        return self.learning_records.find_one({"table_id": table_id})
    
    def add_learning_record(self, table_id, flag):
        """
        Add learning record
        
        Args:
            table_id: Table ID
            flag: Learning flag
            
        Returns:
            pymongo.results.InsertOneResult: Insert result
        """
        record = {
            "table_id": table_id,
            "flag": flag,
            "first_answer_time": datetime.now()
        }
        return self.learning_records.insert_one(record)
    
    def update_learning_record_flag(self, table_id, flag):
        """
        Update learning record flag
        
        Args:
            table_id: Table ID
            flag: New learning flag
            
        Returns:
            pymongo.results.UpdateResult: Update result
        """
        return self.learning_records.update_one(
            {"table_id": table_id},
            {"$set": {"flag": flag}}
        )
    
    def get_teaching_record(self, table_id):
        """
        Get teaching record
        
        Args:
            table_id: Table ID
            
        Returns:
            dict: Teaching record
        """
        return self.teaching_records.find_one({"table_id": table_id})
    
    def add_teaching_record(self, record):
        """
        Add teaching record
        
        Args:
            record: Teaching record data
            
        Returns:
            pymongo.results.InsertOneResult: Insert result
        """
        return self.teaching_records.insert_one(record)
    
    def get_error_record(self, table_id):
        """
        Get error record
        
        Args:
            table_id: Table ID
            
        Returns:
            dict: Error record
        """
        return self.error_records.find_one({"table_id": table_id})
    
    def add_error_record(self, record):
        """
        Add error record
        
        Args:
            record: Error record data
            
        Returns:
            pymongo.results.InsertOneResult: Insert result
        """
        return self.error_records.insert_one(record)

    def search_similar_questions_by_text(self, question):
        """
        Search similar questions using text index
        
        Args:
            question: User question
            
        Returns:
            list: List of records containing questions and IDs
        """
        # Use text search to find related questions
        pipeline = [
            {
                "$match": {
                    "$text": {"$search": question}
                }
            },
            {
                "$project": {
                    "table_id": 1,
                    "question": 1,
                    "score": {"$meta": "textScore"},
                    "_id": 0
                }
            },
            {"$sort": {"score": -1}},
        ]
        
        cursor = self.knowledge_db.aggregate(pipeline)
        text_search_results = list(cursor)
        
        return text_search_results

    
    def update_learning_record_with_rethink(self, table_id, flag, rethink_summary):
        """
        Update learning record flag and rethink_summary
        
        Args:
            table_id: Table ID
            flag: New learning flag
            rethink_summary: Student reflection summary
            
        Returns:
            pymongo.results.UpdateResult: Update result
        """
        return self.learning_records.update_one(
            {"table_id": table_id},
            {
                "$set": {
                    "flag": flag,
                    "rethink_summary": rethink_summary
                }
            },
            upsert=True  # Insert new record if it doesn't exist
        )
    
    def update_learning_record_guidance_error_count(self, table_id, guidance_error_count):
        """
        Update guidance_error_count field in learning record
        
        Args:
            table_id: Table ID
            guidance_error_count: Guidance error count
            
        Returns:
            pymongo.results.UpdateResult: Update result
        """
        return self.learning_records.update_one(
            {"table_id": table_id},
            {
                "$set": {
                    "guidance_error_count": guidance_error_count
                }
            },
            upsert=True  # Insert new record if it doesn't exist
        )
    
    def update_teaching_record(self, table_id, teaching_record):
        """
        Update teaching record
        
        Args:
            table_id: Table ID
            teaching_record: Teaching record data
            
        Returns:
            pymongo.results.UpdateResult: Update result
        """
        return self.teaching_records.update_one(
            {"table_id": table_id},
            {"$set": teaching_record},
            upsert=True  # Insert new record if it doesn't exist
        )
    
    def delete_teaching_record(self, table_id):
        """
        Delete teaching record
        
        Args:
            table_id: Table ID
            
        Returns:
            pymongo.results.DeleteResult: Delete result
        """
        return self.teaching_records.delete_one({"table_id": table_id})
    
    def add_or_update_learning_record(self, table_id, flag, **kwargs):
        """
        Add or update learning record (general method)
        
        Args:
            table_id: Table ID
            flag: Learning flag
            **kwargs: Other fields (like rethink_summary, guidance_error_count, etc.)
            
        Returns:
            pymongo.results.UpdateResult: Update result
        """
        update_data = {"flag": flag}
        update_data.update(kwargs)
        
        return self.learning_records.update_one(
            {"table_id": table_id},
            {"$set": update_data},
            upsert=True
        )
    
    def get_learning_records_by_flag(self, flag):
        """
        Get learning records by flag value
        
        Args:
            flag: Learning flag
            
        Returns:
            list: List of learning records
        """
        return list(self.learning_records.find({"flag": flag}))
    
    def batch_get_learning_records(self, table_ids):
        """
        Batch get learning records
        
        Args:
            table_ids: List of table IDs
            
        Returns:
            dict: Dictionary of learning records with table_id as key
        """
        if not table_ids:
            return {}
        
        cursor = self.learning_records.find({"table_id": {"$in": table_ids}})
        records = list(cursor)
        
        return {record["table_id"]: record for record in records}
    
    def get_teaching_records_with_strategy(self, strategy_type=None):
        """
        Get teaching records (can be filtered by strategy type)
        
        Args:
            strategy_type: Strategy type (optional)
            
        Returns:
            list: List of teaching records
        """
        query = {}
        if strategy_type:
            query["strategy_type"] = strategy_type
        
        return list(self.teaching_records.find(query))
    
    def clear_guidance_error_count(self, table_id):
        """
        Clear guidance_error_count field in learning record
        
        Args:
            table_id: Table ID
            
        Returns:
            pymongo.results.UpdateResult: Update result
        """
        return self.learning_records.update_one(
            {"table_id": table_id},
            {"$unset": {"guidance_error_count": ""}}
        )
    
    def get_statistics(self):
        """
        Get database statistics
        
        Returns:
            dict: Statistics information
        """
        stats = {}
        
        # Learning records statistics
        learning_pipeline = [
            {"$group": {"_id": "$flag", "count": {"$sum": 1}}}
        ]
        learning_stats = list(self.learning_records.aggregate(learning_pipeline))
        stats["learning_records"] = {str(item["_id"]): item["count"] for item in learning_stats}
        
        # Teaching records statistics
        teaching_pipeline = [
            {"$group": {"_id": "$strategy_type", "count": {"$sum": 1}}}
        ]
        teaching_stats = list(self.teaching_records.aggregate(teaching_pipeline))
        stats["teaching_records"] = {item["_id"]: item["count"] for item in teaching_stats}
        
        # Error records statistics
        stats["error_records"] = self.error_records.count_documents({})
        
        # Knowledge database statistics
        stats["knowledge_records"] = self.knowledge_db.count_documents({})
        
        return stats

    def fetch_records_by_ids(self, id_list):
        """
        Get complete records by ID list
        
        Args:
            id_list: List of table IDs
            
        Returns:
            list: Complete record list sorted by original order
        """
        if not id_list:
            return []
        
        # Use $in operator for batch query
        cursor = self.knowledge_db.find(
            {"table_id": {"$in": id_list}}, 
            {
                "table_id": 1, 
                "question": 1,
                "sk_embedding": 1, 
                "table_structure": 1,
                "_id": 0
            }
        )
        
        # Convert to dictionary for quick lookup
        records = list(cursor)
        id_to_record = {record['table_id']: record for record in records}
        
        # Re-sort by original ID list order
        ordered_records = []
        for record_id in id_list:
            if record_id in id_to_record:
                ordered_records.append(id_to_record[record_id])
        
        return ordered_records
    
    def get_guidance_knowledge_with_lookup(self):
        """
        Use MongoDB $lookup operator (similar to SQL JOIN) to get all guidance records and corresponding knowledge data
        
        Returns:
            list: List containing guidance records and corresponding knowledge data
        """
        pipeline = [
            {
                "$lookup": {
                    "from": "MutiKnowledgeDataBase",  # Collection to join
                    "localField": "table_id",          # Field in guidance records
                    "foreignField": "table_id",              # Field in knowledge database
                    "as": "knowledge_data"             # Result field name
                }
            },
            {
                "$unwind": {
                    "path": "$knowledge_data",
                    "preserveNullAndEmptyArrays": False  # Only keep successfully matched documents
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "table_id": 1,
                    "strategy_type": 1,
                    "question": "$knowledge_data.question"  # Only extract question field
                }
            }
        ]
        
        results = list(self.teaching_records.aggregate(pipeline))
        return results

    # --- User Management ---
    def create_user(self, username, password_hash):
        if self.users.find_one({"username": username}):
            return None
        return self.users.insert_one({
            "username": username,
            "password_hash": password_hash,
            "created_at": datetime.now()
        })

    def get_user_by_username(self, username):
        return self.users.find_one({"username": username})

    # --- Chat Session Management ---
    def save_chat_session(self, user_id, session_id, title, messages):
        """Save or update a chat session."""
        return self.chat_sessions.update_one(
            {"session_id": session_id, "user_id": user_id},
            {
                "$set": {
                    "title": title,
                    "messages": messages,
                    "updated_at": datetime.now()
                },
                "$setOnInsert": {
                    "created_at": datetime.now()
                }
            },
            upsert=True
        )

    def get_user_sessions(self, user_id):
        """Get all session titles for a user."""
        return list(self.chat_sessions.find(
            {"user_id": user_id},
            {"messages": 0}  # Don't return messages in summary list
        ).sort("updated_at", -1))

    def get_chat_session(self, user_id, session_id):
        """Get full session data."""
        return self.chat_sessions.find_one({"session_id": session_id, "user_id": user_id})

    def delete_chat_session(self, user_id, session_id):
        """Delete a specific session."""
        return self.chat_sessions.delete_one({"session_id": session_id, "user_id": user_id})

    # --- Result Cache Management ---
    def save_result_cache(self, session_id, data):
        """Save specialized analytical result to cache."""
        return self.result_cache_col.update_one(
            {"session_id": session_id},
            {"$set": {"data": data, "updated_at": datetime.now()}},
            upsert=True
        )

    def get_result_cache(self, session_id):
        """Retrieve specialized analytical result from cache."""
        record = self.result_cache_col.find_one({"session_id": session_id})
        return record["data"] if record else None

    # --- Multi-turn Session Context ---
    def get_session_context(self, conversation_id: str) -> Dict[str, Any]:
        """Retrieve multi-turn context (table_hash, history, etc.)."""
        session = self.multi_turn_sessions.find_one({"conversation_id": conversation_id})
        if not session:
            return {"table_hash": "", "history": [], "reasoning_summary": ""}
        return {
            "table_hash": session.get("table_hash", ""),
            "history": session.get("history", []),
            "reasoning_summary": session.get("reasoning_summary", "")
        }

    def update_session_history(self, conversation_id: str, table_hash: str, question: str, answer: str, reasoning_summary: str = ""):
        """Append a new turn to the conversation history."""
        new_turn = {
            "question": question,
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        }
        update_doc = {
            "$push": {"history": {"$each": [new_turn], "$slice": -10}}, # Keep last 10 turns
            "$set": {
                "table_hash": table_hash,
                "updated_at": datetime.now()
            }
        }
        if reasoning_summary:
            update_doc["$set"]["reasoning_summary"] = reasoning_summary
            
        return self.multi_turn_sessions.update_one(
            {"conversation_id": conversation_id},
            update_doc,
            upsert=True
        )

    def reset_session_context(self, conversation_id: str, new_table_hash: str):
        """Reset history when the table changes."""
        return self.multi_turn_sessions.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "table_hash": new_table_hash,
                    "history": [],
                    "reasoning_summary": "",
                    "updated_at": datetime.now()
                }
            },
            upsert=True
        )

if __name__ == "__main__":
    db = DatabaseManager()
    print(db.get_knowledge_by_id("nt-0"))