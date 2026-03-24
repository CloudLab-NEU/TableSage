import api from './index'

export interface TableData {
    header: string[]
    rows: any[][]
}

export interface ChatRequest {
    question: string
    table?: TableData
    flag?: boolean
    conversation_id?: string
    session_id?: string
}

export interface ProcessingStep {
    step: string
    message?: string
    similar_questions?: string[]
    similarity_scores?: number[]
    answer_result?: any
    final_result?: any
    tool?: string
    result_summary?: string
    error?: string
    timestamp: Date
}

export const chatService = {
    answer: (data: ChatRequest): Promise<any> => api.post('/chat/answer', data),

    answerStream: async (data: ChatRequest) => {
        // Use baseURL from axios config if available, fallback to hardcoded for fetch
        const baseURL = (api.defaults.baseURL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')
        
        const response = await fetch(`${baseURL}/chat/answer`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: data.question,
                table: data.table,
                flag: data.flag,
                conversation_id: data.conversation_id,
                session_id: data.session_id
            }),
        })
        return response
    },

    generateReport: (sessionId: string): Promise<any> => api.post(`/chat/generate-report/${sessionId}`),
}

export const fileService = {
    getDownloadUrl: (fileId: string) => `http://127.0.0.1:8000/api/files/download/${fileId}`
}
