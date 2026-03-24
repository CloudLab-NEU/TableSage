<script setup lang="ts">
import { ref, nextTick, computed, onMounted, onActivated, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import api from '../../api'
const router = useRouter()
const route = useRoute()

interface Message {
  id: number
  content: string
  type: 'user' | 'assistant'
  timestamp: Date
  files?: FileInfo[]
  isProcessing?: boolean
  status?: string
  error?: string
  processingSteps?: ProcessingStep[]
  question?: string
  table?: TableData
  generatedImage?: string
  reportSummary?: string
  reportUrl?: string
}

interface RagDetail {
  table_id: string
  question: string
  score: number
}

interface ProcessingStep {
  step: string
  message?: string
  similar_questions?: string[]
  similar_questions_details?: RagDetail[]
  tool?: string
  result?: any
  result_summary?: string
  answer_result?: any
  final_result?: any
  timestamp: Date
}

interface TableData {
  header: string[]
  rows: any[][]
}

interface FileInfo {
  id: string
  name: string
  size: number
  type: string
  url: string
}

interface JsonDataFormat {
  header: string[]
  rows: any[][]
}

interface ChatHistory {
  id: string
  title: string
  messages: Message[]
  createdAt: Date
  updatedAt: Date
}

interface Settings {
  apiUrl: string
  apiKey: string
  modelName: string
  topN: number
  confidence: number
}

const messages = ref<Message[]>([
  {
    id: 1,
    content: '你好！我是 TableSage AI 助手，有什么可以帮助你的吗？',
    type: 'assistant',
    timestamp: new Date()
  }
])

const inputMessage = ref('')
const isLoading = ref(false)
const chatContainer = ref<HTMLElement>()
const fileInput = ref<HTMLInputElement>()
const selectedFiles = ref<FileInfo[]>([])
const showSidebar = ref(true)
const graph_flag = ref(false)
const latestSessionId = ref<string | null>(null)
const isGeneratingReport = ref(false)

const chatHistories = ref<ChatHistory[]>([])
const currentChatId = ref<string | null>(null)
const currentUser = ref<any>(null)

const showSettings = ref(false)
const settings = ref<Settings>({
  apiUrl: 'https://api.openai.com/v1',
  apiKey: '',
  modelName: 'gpt-4',
  topN: 5,
  confidence: 0.8
})

const modelOptions = [
  { value: 'gpt-4', label: 'GPT-4' },
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
  { value: 'claude-3-opus', label: 'Claude 3 Opus' },
  { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet' },
  { value: 'claude-3-haiku', label: 'Claude 3 Haiku' },
  { value: 'deepseek-chat', label: 'DeepSeek' }
]

const encryptApiKey = (apiKey: string): string => {
  if (!apiKey) return ''
  return btoa(apiKey)
}

const decryptApiKey = (encryptedApiKey: string): string => {
  if (!encryptedApiKey) return ''
  try {
    return atob(encryptedApiKey)
  } catch (error) {
    console.error('解密API密钥失败:', error)
    return ''
  }
}

const adjustTextareaHeight = () => {
}

const generateChatTitle = (firstMessage: string): string => {
  const cleanMessage = firstMessage.trim()
  if (cleanMessage.length <= 20) return cleanMessage
  return cleanMessage.substring(0, 20) + '...'
}

const parseInputContent = (input: string): { question: string; table: TableData | null } => {
  try {
    const tableDataIndex = input.indexOf('表格数据：')

    if (tableDataIndex !== -1) {
      const question = input.substring(0, tableDataIndex).trim()
      const tableDataStr = input.substring(tableDataIndex + 5).trim()

      try {
        const tableData = JSON.parse(tableDataStr)
        if (validateJsonData(tableData)) {
          return {
            question: question,
            table: {
              header: tableData.header,
              rows: tableData.rows
            }
          }
        }
      } catch (error) {
        console.error('解析表格数据失败:', error)
      }
    }

    // 尝试解析纯 JSON 格式
    try {
      const parsedJson = JSON.parse(input)
      if (parsedJson && typeof parsedJson === 'object' && parsedJson.question && parsedJson.table) {
        if (validateJsonData(parsedJson.table)) {
          return {
            question: parsedJson.question,
            table: {
              header: parsedJson.table.header,
              rows: parsedJson.table.rows
            }
          }
        }
      }
    } catch (e) {
      // 并非纯 JSON，静默失败，使用原字符串作为问题
    }

    return { question: input, table: null }
  } catch (error) {
    console.error('解析输入内容失败:', error)
    return { question: input, table: null }
  }
}

const validateJsonData = (jsonData: any): boolean => {
  if (!jsonData || typeof jsonData !== 'object') {
    return false
  }

  if (jsonData.header && jsonData.rows) {
    return Array.isArray(jsonData.header) && Array.isArray(jsonData.rows)
  }

  return false
}

const mergeMultipleTables = (tables: JsonDataFormat[]): JsonDataFormat => {
  if (tables.length === 0) {
    return { header: [], rows: [] }
  }

  if (tables.length === 1) {
    return tables[0]
  }

  const allHeaders: string[] = []
  const headerSet = new Set<string>()

  tables.forEach(table => {
    table.header.forEach(header => {
      if (!headerSet.has(header)) {
        headerSet.add(header)
        allHeaders.push(header)
      }
    })
  })

  const mergedHeader = allHeaders

  const commonColumns = findCommonColumns(tables)

  if (commonColumns.length > 0) {
    const mergedRows = mergeByCommonColumns(tables, mergedHeader, commonColumns)
    return {
      header: mergedHeader,
      rows: mergedRows
    }
  } else {
    const mergedRows: any[][] = []

    tables.forEach(table => {
      table.rows.forEach(row => {
        const newRow = new Array(mergedHeader.length).fill('')

        table.header.forEach((header, index) => {
          const mergedIndex = mergedHeader.indexOf(header)
          if (mergedIndex !== -1 && index < row.length) {
            newRow[mergedIndex] = row[index] || ''
          }
        })

        mergedRows.push(newRow)
      })
    })

    return {
      header: mergedHeader,
      rows: mergedRows
    }
  }
}

const findCommonColumns = (tables: JsonDataFormat[]): string[] => {
  if (tables.length < 2) return []

  const commonHeaders: string[] = []

  tables[0].header.forEach(header => {
    const isCommonToAll = tables.every(table => table.header.includes(header))
    if (isCommonToAll) {
      commonHeaders.push(header)
    }
  })

  return commonHeaders
}

const mergeByCommonColumns = (tables: JsonDataFormat[], mergedHeader: string[], commonColumns: string[]): any[][] => {
  const mergedRows: any[][] = []

  const keyColumn = commonColumns[0]

  const allKeys = new Set<string>()
  tables.forEach(table => {
    const keyIndex = table.header.indexOf(keyColumn)
    if (keyIndex !== -1) {
      table.rows.forEach(row => {
        if (row[keyIndex]) {
          allKeys.add(String(row[keyIndex]))
        }
      })
    }
  })

  allKeys.forEach(keyValue => {
    const newRow = new Array(mergedHeader.length).fill('')

    tables.forEach(table => {
      const keyIndex = table.header.indexOf(keyColumn)
      if (keyIndex !== -1) {
        const matchingRow = table.rows.find(row => String(row[keyIndex]) === keyValue)
        if (matchingRow) {
          table.header.forEach((header, index) => {
            const mergedIndex = mergedHeader.indexOf(header)
            if (mergedIndex !== -1 && index < matchingRow.length) {
              const value = matchingRow[index]
              if (newRow[mergedIndex] === '' || newRow[mergedIndex] === null || newRow[mergedIndex] === undefined) {
                newRow[mergedIndex] = value || ''
              }
            }
          })
        }
      }
    })

    mergedRows.push(newRow)
  })

  return mergedRows
}

const parseMultiTableJson = (jsonData: any): JsonDataFormat[] => {
  const tables: JsonDataFormat[] = []

  if (validateJsonData(jsonData)) {
    tables.push(jsonData)
    return tables
  }

  if (Array.isArray(jsonData)) {
    jsonData.forEach(item => {
      if (validateJsonData(item)) {
        tables.push(item)
      }
    })
    return tables
  }

  if (typeof jsonData === 'object' && jsonData !== null) {
    const findTables = (obj: any) => {
      if (validateJsonData(obj)) {
        tables.push(obj)
        return
      }

      if (Array.isArray(obj)) {
        obj.forEach(item => findTables(item))
      } else if (typeof obj === 'object' && obj !== null) {
        Object.values(obj).forEach(value => findTables(value))
      }
    }

    findTables(jsonData)
  }

  return tables
}

const generateImage = async (question: string, table: TableData): Promise<string | null> => {
  try {
    const { chatService } = await import('../../api/services')
    const result = await chatService.answer({
      question,
      table,
      flag: graph_flag.value
    })

    console.log('Image Generation API Response:', result)

    if (result.tool_calls && result.tool_calls.length > 0) {
      const toolCall = result.tool_calls[0]
      if (toolCall.result) {
        console.log('Generated image URL:', toolCall.result)
        return toolCall.result
      }
    }

    return null
  } catch (error) {
    console.error('图像生成失败:', error)
    throw error
  }
}

const processAnswerStream = async (question: string, table: TableData, useAnswerStreamAPI: boolean = false): Promise<void> => {
  let messageIndex: number | undefined
  try {
    const { chatService } = await import('../../api/services')

    const requestBody: any = {
      question,
      table
    }

    if (!useAnswerStreamAPI) {
      requestBody.flag = graph_flag.value
    }

    const response = await chatService.answerStream({
      question: requestBody.question,
      table: requestBody.table,
      flag: graph_flag.value,
      conversation_id: currentChatId.value || undefined
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    console.log(`${useAnswerStreamAPI ? 'Answer Stream' : 'Chat Answer'} API Response:`, response)
    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('无法获取响应流')
    }

    const assistantMessage: Message = {
      id: Date.now() + 1,
      content: '',
      type: 'assistant',
      timestamp: new Date(),
      isProcessing: true,
      processingSteps: []
    }

    messages.value.push(assistantMessage)
    messageIndex = messages.value.length - 1

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()

      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')

      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmedLine = line.trim()
        if (trimmedLine.startsWith('data: ')) {
          try {
            const data = JSON.parse(trimmedLine.substring(6))

            if (data.session_id) {
              console.log('🔑 流式处理 Session ID:', data.session_id)
              latestSessionId.value = data.session_id
            }

            const steps = messages.value[messageIndex].processingSteps || []
            const lastStep = steps.length > 0 ? steps[steps.length - 1] : null
            
            const step: ProcessingStep = {
              ...data,
              timestamp: new Date()
            }

            if (!lastStep || lastStep.step !== data.step || (data.message && lastStep.message !== data.message)) {
              messages.value[messageIndex].processingSteps?.push(step)
            }

            if (data.step === 'start') {
              messages.value[messageIndex].status = '开始处理问题...'
            } else if (data.step === 'router') {
              messages.value[messageIndex].status = `意图分析: ${data.plan?.intent || '分析中'}`
            } else if (data.step === 'rag' || data.step === 'rag_done') {
              messages.value[messageIndex].status = `正在检索相似问题...`
            } else if (data.step === 'thinking') {
              messages.value[messageIndex].status = `正在计划下一步...`
            } else if (data.step === 'tool_call') {
              messages.value[messageIndex].status = `正在使用工具分析数据...`
            } else if (data.step === 'tool_result') {
              messages.value[messageIndex].status = `工具执行完毕...`
            } else if (data.step === 'visualization_start') {
              messages.value[messageIndex].status = `正在生成可视化图表...`
            } else if (data.step === 'visualization_done') {
              messages.value[messageIndex].status = data.message || `图表生成完毕`
              if (data.tool_calls && data.tool_calls.length > 0) {
                 const chartCall = data.tool_calls.find((t: any) => t.name !== 'none');
                 if (chartCall && chartCall.content) {
                    messages.value[messageIndex].generatedImage = chartCall.content;
                 } else if (chartCall && chartCall.result && chartCall.result !== 'MCP Tool 调用成功') {
                    messages.value[messageIndex].generatedImage = chartCall.result;
                 }
              }
            } else if (data.step === 'report_start') {
              messages.value[messageIndex].status = `正在生成分析报告...`
            } else if (data.step === 'report_status') {
              messages.value[messageIndex].status = data.message
            } else if (data.step === 'report_chunk') {
              if (!messages.value[messageIndex].reportSummary) {
                messages.value[messageIndex].reportSummary = ''
              }
              messages.value[messageIndex].reportSummary += data.content
            } else if (data.step === 'report_done') {
              messages.value[messageIndex].status = data.message || `报告生成完毕`
              if (data.summary && !messages.value[messageIndex].reportSummary) {
                messages.value[messageIndex].reportSummary = data.summary
              }
              if (data.download_url) {
                 messages.value[messageIndex].reportUrl = data.download_url
              }
            } else if (data.step === 'final' || data.step === 'end' || data.step === 'task_done') {
              if (data.answer) {
                messages.value[messageIndex].content = data.answer
              } else if (data.complete_result?.answer) {
                 messages.value[messageIndex].content = data.complete_result.answer
              } else if (data.final_result) {
                messages.value[messageIndex].content = data.final_result.answer
              }
              
              if (data.step === 'task_done' || (data.step === 'end' && !isGeneratingReport && !graph_flag.value)) {
                messages.value[messageIndex].isProcessing = false
                messages.value[messageIndex].status = ''
              }
            } else if (data.step === 'error') {
               messages.value[messageIndex].error = data.error || '流程执行失败'
               messages.value[messageIndex].isProcessing = false
               messages.value[messageIndex].status = ''
            }

            await nextTick()
            scrollToBottom()

          } catch (e) {
            console.error('解析流数据失败:', e, line)
          }
        }
      }
    }

    // Ensure processing is marked as finished when stream ends
    if (messages.value[messageIndex]) {
      messages.value[messageIndex].isProcessing = false
      messages.value[messageIndex].status = ''
    }

    saveCurrentChat()
  } catch (error) {
    console.error('答题流式处理失败:', error)
    // 出现异常时，尝试在当前的消息卡片中显示错误
    if (typeof messageIndex !== 'undefined' && messages.value[messageIndex]) {
      messages.value[messageIndex].error = `处理失败: ${error instanceof Error ? error.message : '未知错误'}`
      messages.value[messageIndex].isProcessing = false
      messages.value[messageIndex].status = ''
    } else {
      // 如果没有当前消息轨道，才直接 Push 报错
      const errorMessage: Message = {
        id: Date.now() + 2,
        content: `系统异常: ${error instanceof Error ? error.message : '网络或底层错误'}`,
        type: 'assistant',
        timestamp: new Date()
      }
      messages.value.push(errorMessage)
    }
    saveCurrentChat()
    await nextTick()
    scrollToBottom()
  } finally {
    isLoading.value = false
  }
}

const processQuestion = async (question: string, table: TableData): Promise<void> => {
  try {
    if (graph_flag.value) {
      console.log('图片模式：调用 unified answer stream (包含可视化逻辑)')
      await processAnswerStream(question, table, true)
    } else {
      console.log('普通模式：调用chat/answer API进行答题流程')
      await processAnswerStream(question, table, false)
    }
  } catch (error) {
    console.error('问题处理失败:', error)
    // 根据具体错误显示更友好的信息
    const errText = error instanceof Error ? error.message : '未知错误'
    
    // 尽量不使用 push，而是更新最后一条助手消息（如果它是当前正在处理的那条）
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg && lastMsg.type === 'assistant' && lastMsg.isProcessing) {
      lastMsg.error = `处理失败: ${errText}`
      lastMsg.isProcessing = false
      lastMsg.status = ''
    } else {
      const errorMessage: Message = {
        id: Date.now() + 2,
        content: `处理失败: ${errText}`,
        type: 'assistant',
        timestamp: new Date()
      }
      messages.value.push(errorMessage)
    }
    saveCurrentChat()
    await nextTick()
    scrollToBottom()
  } finally {
    isLoading.value = false
  }
}

const persistChatHistories = () => {
  localStorage.setItem('tablesage-chat-histories', JSON.stringify(chatHistories.value))
}

const saveCurrentChat = async () => {
  if (!currentChatId.value || !currentUser.value) return

  const chatIndex = chatHistories.value.findIndex(chat => chat.id === currentChatId.value)
  if (chatIndex !== -1) {
    chatHistories.value[chatIndex] = {
      ...chatHistories.value[chatIndex],
      messages: [...messages.value],
      updatedAt: new Date()
    }

    try {
      await api.post('/chat/sessions', {
        user_id: currentUser.value.user_id,
        session_id: currentChatId.value,
        title: chatHistories.value[chatIndex].title,
        messages: messages.value
      })
    } catch (err) {
      console.error('保存会话失败:', err)
    }
  }
}

const sendMessage = async () => {
  if (isLoading.value) {
    console.warn('⚠️ 正在处理中，忽略多余的发送请求')
    return
  }
  
  if (!inputMessage.value.trim() && selectedFiles.value.length === 0) return

  isLoading.value = true
  const currentInput = inputMessage.value.trim()

  const { question, table } = parseInputContent(currentInput)

  const userMessage: Message = {
    id: Date.now(),
    content: currentInput,
    type: 'user',
    timestamp: new Date(),
    files: selectedFiles.value.length > 0 ? [...selectedFiles.value] : undefined,
    question: question,
    table: table || undefined
  }

  messages.value.push(userMessage)
  inputMessage.value = ''
  selectedFiles.value = []


  if (!currentChatId.value) {
    const newChatId = 'chat_' + Date.now()
    const newChat: ChatHistory = {
      id: newChatId,
      title: generateChatTitle(question || currentInput || '新聊天'),
      messages: [...messages.value],
      createdAt: new Date(),
      updatedAt: new Date()
    }
    chatHistories.value.unshift(newChat)
    currentChatId.value = newChatId
    saveCurrentChat()
  } else {

    saveCurrentChat()
  }


  await nextTick()
  scrollToBottom()


  let activeTable = table
  if (!activeTable) {
    // 追溯历史消息，寻找最近一次包含表格的消息
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].table) {
        activeTable = messages.value[i].table || null
        break
      }
    }
  }

  if (activeTable && question) {
    await processQuestion(question, activeTable as TableData)
  } else {

    setTimeout(() => {
      const assistantMessage: Message = {
        id: Date.now() + 1,
        content: generateMockResponse(currentInput),
        type: 'assistant',
        timestamp: new Date()
      }
      messages.value.push(assistantMessage)
      isLoading.value = false


      saveCurrentChat()

      nextTick(() => scrollToBottom())
    }, 1000 + Math.random() * 2000)
  }
}


const generateMockResponse = (input: string): string => {
  if (!input.trim() && selectedFiles.value.length > 0) {
    return '我看到你上传了文件，但目前我还不能处理文件内容。请告诉我你想了解什么？'
  }


  if (input.includes('表格') || input.includes('header') || input.includes('rows') || input.includes('question')) {
    const graphStatus = graph_flag.value ? '✅ 图表生成已启用' : '❌ 图表生成未启用'
    return `我检测到你可能想要进行表格问答。
    
当前状态：${graphStatus}

请确保按照以下格式输入：

**JSON格式（推荐）：**
\`\`\`json
{
  "question": "你的问题",
  "table": {
    "header": ["列1", "列2", "列3"],
    "rows": [
      ["数据1", "数据2", "数据3"],
      ["数据4", "数据5", "数据6"]
    ]
  }
}
\`\`\`

**或者简单格式：**
问题：你的问题
表格：{"header": ["列1", "列2"], "rows": [["数据1", "数据2"], ["数据3", "数据4"]]}

这样我就能为你提供更准确的答案！`
  }

  const graphStatus = graph_flag.value ? ' (图表生成已启用)' : ' (图表生成未启用)'
  const responses = [
    `关于"${input}"，这是一个很有趣的问题${graphStatus}。如果你有相关的表格数据，我可以为你提供更精确的分析。`,
    `我理解你想了解"${input}"的相关信息${graphStatus}。如果你能提供表格数据，我可以基于数据给出更准确的答案。`,
    `这是一个很好的问题！关于"${input}"${graphStatus}，建议你提供相关的表格数据，这样我可以进行数据分析来回答你的问题。`,
    `感谢你的提问。对于"${input}"这个话题${graphStatus}，如果有数据表格支持，我可以提供更详细的分析和答案。`
  ]
  return responses[Math.floor(Math.random() * responses.length)]
}


const scrollToBottom = () => {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}


const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}


const formatTime = (date: any): string => {
  if (!date) return ''
  const d = date instanceof Date ? date : new Date(date)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}


const formatDate = (date: any): string => {
  if (!date) return ''
  const d = date instanceof Date ? date : new Date(date)
  if (isNaN(d.getTime())) return ''

  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}


const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + ' B'
  else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  else return (bytes / 1048576).toFixed(1) + ' MB'
}


const onImageLoad = (event: Event) => {
  console.log('图片加载成功:', event)
}


const onImageError = (event: Event) => {
  console.error('图片加载失败:', event)
  const img = event.target as HTMLImageElement
  img.style.display = 'none'

}


const triggerFileUpload = () => {
  fileInput.value?.click()
}


const generateReport = async () => {
  if (!latestSessionId.value) {
    console.error('没有可用的 session_id')
    const errorMessage: Message = {
      id: Date.now(),
      content: '无法生成报告：没有找到最近的会话ID',
      type: 'assistant',
      timestamp: new Date()
    }
    messages.value.push(errorMessage)
    saveCurrentChat()
    return
  }

  isGeneratingReport.value = true


  const reportMessage: Message = {
    id: Date.now(),
    content: '正在生成报告...',
    type: 'assistant',
    timestamp: new Date(),
    isProcessing: true
  }
  messages.value.push(reportMessage)


  const updateStatus = (content: string, isCompleted = false) => {
    const messageIndex = messages.value.length - 1
    messages.value[messageIndex].content = content
    if (isCompleted) {
      messages.value[messageIndex].isProcessing = false
    }
  }

  try {
    const { chatService, fileService } = await import('../../api/services')
    console.log('开始生成报告，session_id:', latestSessionId.value)

    const generateResult = await chatService.generateReport(latestSessionId.value)
    const fileId = generateResult.file_id

    if (!fileId) {
      throw new Error('未获取到文件ID')
    }

    updateStatus('正在下载报告...')

    const downloadResponse = await fetch(fileService.getDownloadUrl(fileId))

    if (!downloadResponse.ok) {
      throw new Error(`下载失败: ${downloadResponse.status}`)
    }


    const contentType = downloadResponse.headers.get('content-type')

    if (contentType && (contentType.includes('application/') || contentType.includes('binary'))) {

      const blob = await downloadResponse.blob()
      const downloadUrl = window.URL.createObjectURL(blob)


      const contentDisposition = downloadResponse.headers.get('content-disposition')
      let fileName = `report_${latestSessionId.value}.docx`

      if (contentDisposition) {
        const fileNameMatch = contentDisposition.match(/filename="?([^"]+)"?/)
        if (fileNameMatch) {
          fileName = fileNameMatch[1]
        }
      }


      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = fileName
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)


      window.URL.revokeObjectURL(downloadUrl)
    } else {

      const downloadResult = await downloadResponse.json()
      const downloadUrl = downloadResult.download_url || downloadResult.url

      if (!downloadUrl) {
        throw new Error('未获取到下载链接')
      }


      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = `report_${latestSessionId.value}.docx`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }


    updateStatus('✅ 报告下载完成', true)

  } catch (error) {
    console.error('报告生成失败:', error)
    updateStatus(`❌ 报告生成失败: ${error instanceof Error ? error.message : '未知错误'}`, true)
  } finally {
    isGeneratingReport.value = false
    saveCurrentChat()
  }
}


const toggleGraphFlag = () => {
  graph_flag.value = !graph_flag.value
}


const handleFileSelect = async (event: Event) => {
  const input = event.target as HTMLInputElement
  if (!input.files || input.files.length === 0) return

  const allTables: JsonDataFormat[] = []
  const processedFiles: string[] = []

  for (const file of Array.from(input.files)) {
    try {
      const content = await readFileAsText(file)
      let table: JsonDataFormat | null = null

      if (file.name.toLowerCase().endsWith('.csv') || file.type === 'text/csv') {
        table = parseCsvToJson(content)
      } else {
        const jsonData = JSON.parse(content)
        const tables = parseMultiTableJson(jsonData)
        if (tables.length > 0) {
          table = mergeMultipleTables(tables)
        }
      }

      if (table && table.header.length > 0) {
        allTables.push(table)
        processedFiles.push(file.name)

        const fileInfo: FileInfo = {
          id: Date.now() + Math.random().toString(36).substring(2, 9),
          name: file.name,
          size: file.size,
          type: file.type || (file.name.toLowerCase().endsWith('.csv') ? 'text/csv' : ''),
          url: URL.createObjectURL(file)
        }
        selectedFiles.value.push(fileInfo)
      } else {
        showErrorMessage(`文件 "${file.name}" 中没有找到有效的表格数据`)
      }
    } catch (error) {
      showErrorMessage(`读取或解析文件 "${file.name}" 失败: ${error}`)
    }
  }

  if (allTables.length > 0) {
    const mergedTable = mergeMultipleTables(allTables)
    const currentQuestion = inputMessage.value.trim()
    const formattedData = formatTableDataForInput(mergedTable, currentQuestion)
    inputMessage.value = formattedData

    if (processedFiles.length === 1) {
      showSuccessMessage(`已成功解析文件: ${processedFiles.join(', ')}，表格数据已添加到输入框`)
    } else {
      showSuccessMessage(`已成功解析并拼接 ${processedFiles.length} 个文件（来自: ${processedFiles.join(', ')}），拼接后的表格数据已添加到输入框`)
    }
  }

  input.value = ''
}


const parseCsvToJson = (content: string): JsonDataFormat => {
  const lines = content.split(/\r?\n/)
  if (lines.length === 0) return { header: [], rows: [] }

  const header = lines[0].split(',').map(h => h.trim())
  const rows = lines.slice(1)
    .filter(line => line.trim() !== '')
    .map(line => {
      const values = line.split(',')
      return values.map(v => v.trim())
    })

  return { header, rows }
}

const readFileAsText = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => resolve(e.target?.result as string)
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsText(file, 'utf-8')
  })
}


const formatTableDataForInput = (jsonData: JsonDataFormat, userQuestion: string = ''): string => {
  if (jsonData.header && jsonData.rows) {

    const question = userQuestion || '请在这里输入你的问题'


    const formattedContent = `${question}

表格数据：
${JSON.stringify(jsonData, null, 2)}`

    return formattedContent
  }

  return JSON.stringify(jsonData, null, 2)
}


const showMessage = (content: string): void => {
  const message: Message = {
    id: Date.now(),
    content,
    type: 'assistant',
    timestamp: new Date()
  }
  messages.value.push(message)
  nextTick(() => scrollToBottom())
}

const showSuccessMessage = (content: string) => showMessage(content)
const showErrorMessage = (content: string) => showMessage(content)


const isJsonFile = (file: FileInfo): boolean => {
  return file.type === 'application/json' || file.name.toLowerCase().endsWith('.json')
}

const isCsvFile = (file: FileInfo): boolean => {
  return file.type === 'text/csv' || file.name.toLowerCase().endsWith('.csv')
}


const removeFile = (fileId: string) => {
  const fileIndex = selectedFiles.value.findIndex(f => f.id === fileId)
  if (fileIndex !== -1) {

    URL.revokeObjectURL(selectedFiles.value[fileIndex].url)
    selectedFiles.value.splice(fileIndex, 1)
  }
}


const createNewChat = () => {

  if (currentChatId.value) {
    saveCurrentChat()
  }


  currentChatId.value = null
  messages.value = [
    {
      id: Date.now(),
      content: '你好！我是 TableSage AI 助手，有什么可以帮助你的吗？',
      type: 'assistant',
      timestamp: new Date()
    }
  ]


  inputMessage.value = ''
  selectedFiles.value = []
  isLoading.value = false
}


const selectChat = async (chatId: string) => {
  if (currentChatId.value === chatId) return

  const oldChatId = currentChatId.value
  if (oldChatId) {
    // Make saveCurrentChat non-blocking
    saveCurrentChat().catch(err => console.error('Background save failed:', err))
  }

  const chat = chatHistories.value.find(c => c.id === chatId)
  if (chat && currentUser.value) {
    currentChatId.value = chatId
    try {
      const res = await api.get(`/chat/sessions/${currentUser.value.user_id}/${chatId}`) as any
      if (res && res.messages) {
        messages.value = [...res.messages]
      } else if (Array.isArray(res)) {
        // Fallback if backend returns list directly for some reason
        messages.value = [...res]
      }
    } catch (err) {
      console.error('获取会话详情失败:', err)
      messages.value = []
    }
    nextTick(() => scrollToBottom())
  }
}

const deleteChat = async (chatId: string, event: Event) => {
  event.stopPropagation()
  if (!currentUser.value) return

  const chatIndex = chatHistories.value.findIndex(c => c.id === chatId)
  if (chatIndex !== -1) {
    chatHistories.value.splice(chatIndex, 1)

    try {
      await api.delete(`/chat/sessions/${currentUser.value.user_id}/${chatId}`)
    } catch (err) {
      console.error('删除会话失败:', err)
    }

    if (currentChatId.value === chatId) {
      createNewChat()
    }
  }
}


const toggleSidebar = () => {
  showSidebar.value = !showSidebar.value
}


const openSettings = () => {
  showSettings.value = true
}


const closeSettings = () => {
  showSettings.value = false
}


const saveSettings = async () => {
  try {

    const configRequest = {
      apiUrl: settings.value.apiUrl,
      apiKey: encryptApiKey(settings.value.apiKey),
      modelName: settings.value.modelName,
      confidence: settings.value.confidence,
      topN: settings.value.topN
    }


    const response = await fetch('http://127.0.0.1:8000/config/update', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(configRequest)
    })

    if (!response.ok) {
      throw new Error(`保存配置失败: ${response.status}`)
    }

    const result = await response.json()
    console.log('配置保存成功:', result)


    localStorage.setItem('tablesage-settings', JSON.stringify(settings.value))


    const successMessage: Message = {
      id: Date.now(),
      content: '✅ 配置保存成功',
      type: 'assistant',
      timestamp: new Date()
    }
    messages.value.push(successMessage)

    showSettings.value = false
    saveCurrentChat()

  } catch (error) {
    console.error('保存配置失败:', error)


    const errorMessage: Message = {
      id: Date.now(),
      content: `❌ 配置保存失败: ${error instanceof Error ? error.message : '未知错误'}`,
      type: 'assistant',
      timestamp: new Date()
    }
    messages.value.push(errorMessage)
    saveCurrentChat()
  }
}


const resetSettings = () => {
  settings.value = {
    apiUrl: 'https://api.openai.com/v1',
    apiKey: '',
    modelName: 'gpt-4',
    topN: 5,
    confidence: 0.7
  }
}


const loadSettings = async () => {
  try {
    const result = await api.get('/config/current') as any
    if (result.env_config) {
      settings.value = {
        apiUrl: result.env_config.apiUrl || settings.value.apiUrl,
        apiKey: result.env_config.apiKey ? decryptApiKey(result.env_config.apiKey) : settings.value.apiKey,
        modelName: result.env_config.modelName || settings.value.modelName,
        topN: result.params?.topN || settings.value.topN,
        confidence: result.params?.confidence || settings.value.confidence
      }
      console.log('从后端加载配置成功:', result)
    }
  } catch (error) {
    console.warn('从后端加载配置失败，使用本地存储:', error)
  }


  const savedSettings = localStorage.getItem('tablesage-settings')
  if (savedSettings) {
    try {
      const localSettings = JSON.parse(savedSettings)

      settings.value = { ...settings.value, ...localSettings }
    } catch (error) {
      console.error('加载本地设置失败:', error)
    }
  }
}



onMounted(async () => {
  await initChat()
})

onActivated(async () => {
  await initChat()
})

// Add watcher for route changes to handle navigation from login
watch(() => route.path, async () => {
  await initChat()
})

const initChat = async () => {
  const userJson = localStorage.getItem('tablesage-user')
  if (userJson) {
    const newUser = JSON.parse(userJson)
    // Only refresh if user changed or was null
    if (!currentUser.value || currentUser.value.user_id !== newUser.user_id || !currentUser.value.username) {
      currentUser.value = newUser
      await loadChatHistories()

      if (chatHistories.value.length === 0) {
        createNewChat()
      } else {
        // If we don't have a current chat selected, pick the first one
        if (!currentChatId.value) {
          await selectChat(chatHistories.value[0].id)
        }
      }
    }
  } else {
    // If we're not on login page, go there
    if (route.path !== '/login') {
      handleLogout()
    }
  }
}

const handleLogout = () => {
  localStorage.removeItem('tablesage-user')
  currentUser.value = null
  window.location.href = '#/login'
}

const loadChatHistories = async () => {
  if (!currentUser.value) return
  try {
    const res = await api.get(`/chat/sessions/${currentUser.value.user_id}`) as any
    chatHistories.value = res.map((s: any) => ({
      id: s.session_id,
      title: s.title,
      messages: [], // Full messages loaded on selection
      updatedAt: new Date(s.updated_at)
    }))
  } catch (err) {
    console.error('加载历史记录失败:', err)
  }
}


const isSendDisabled = computed(() => {
  return (inputMessage.value.trim() === '' && selectedFiles.value.length === 0) || isLoading.value
})





const getStepName = (step: string): string => {
  const stepNames: { [key: string]: string } = {
    'start': '初始化',
    'rag': '开始检索 (RAG)',
    'rag_done': '检索结果',
    'thinking': '智能思考中',
    'tool_call': '调用工具',
    'tool_result': '工具结果',
    'similar_search': '搜索相似问题',
    'answering': '分析答案',
    'final': '生成最终答案',
    'error': '处理异常',
    'end': '处理完成'
  }
  return stepNames[step] || step
}


const getStepIconClass = (step: string): string => {
  const iconClasses: { [key: string]: string } = {
    'start': 'step-icon-start',
    'rag': 'step-icon-search',
    'rag_done': 'step-icon-search',
    'thinking': 'step-icon-processing',
    'tool_call': 'step-icon-tool',
    'tool_result': 'step-icon-tool-result',
    'similar_search': 'step-icon-search',
    'answering': 'step-icon-processing',
    'final': 'step-icon-final',
    'error': 'step-icon-error',
    'end': 'step-icon-complete',
    'think': 'step-icon-think'
  }
  return iconClasses[step] || 'step-icon-default'
}


const extractReasoning = (answer: string): string => {
  if (!answer) return ''
  const thinkStart = answer.indexOf('<think>')
  const thinkEnd = answer.indexOf('</think>')
  
  if (thinkStart !== -1) {
    if (thinkEnd !== -1) {
      return answer.substring(thinkStart + 7, thinkEnd).trim()
    } else {
      return answer.substring(thinkStart + 7).trim()
    }
  }
  
  // Fallback for models that output <Answer> but no <think>
  const answerStart = answer.indexOf('<Answer>')
  if (answerStart > 0) {
    return answer.substring(0, answerStart).trim()
  }
  
  return ''
}

const formatFinalAnswer = (answer: string): string => {
  if (!answer) return ''
  
  const answerStart = answer.indexOf('<Answer>')
  const answerEnd = answer.indexOf('</Answer>')
  
  if (answerStart !== -1) {
    if (answerEnd !== -1) {
      return answer.substring(answerStart + 8, answerEnd).trim()
    } else {
      return answer.substring(answerStart + 8).trim()
    }
  }
  
  const thinkEnd = answer.indexOf('</think>')
  if (thinkEnd !== -1) {
    return answer.substring(thinkEnd + 8).trim()
  }
  
  const thinkStart = answer.indexOf('<think>')
  if (thinkStart !== -1) {
    return answer.substring(0, thinkStart).trim()
  }
  
  return answer.trim()
}


const extractGuidanceConfidence = (step: any): number | null => {
  if (step.step === 'guidance_result' && step.guidance_result?.recalculated_confidence !== undefined) {
    return step.guidance_result.recalculated_confidence
  }
  return null
}

const getScoreClass = (score: number) => {
  if (score >= 0.9) return 'score-high'
  if (score >= 0.7) return 'score-medium'
  return 'score-low'
}

</script>

<template>
  <div class="app-container">
    <div class="sidebar" :class="{ 'sidebar-hidden': !showSidebar }">

      <div class="sidebar-actions">
        <button class="new-chat-btn" @click="createNewChat">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 5v14M5 12h14" />
          </svg>
          新聊天
        </button>
      </div>

      <!-- User Info & Logout -->
      <div v-if="currentUser" class="sidebar-user">
        <div class="user-info">
          <div class="user-avatar">{{ currentUser?.username?.charAt(0).toUpperCase() || 'U' }}</div>
          <span class="username">{{ currentUser?.username || '用户' }}</span>
        </div>
        <button @click="handleLogout" class="logout-btn" title="退出登录">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" />
          </svg>
        </button>
      </div>

      <div class="sidebar-nav">
        <button class="nav-item active">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          聊天
        </button>
        <button class="nav-item" @click="openSettings">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M12 1v6m0 6v6m11-7h-6m-6 0H1m15.5-3.5L19 4.5m-14 14L7.5 16M4.5 19l2.5-2.5m14-14L18.5 4.5"></path>
          </svg>
          设置
        </button>
      </div>

      <div class="chat-history">
        <div class="chat-history-header">
          <span>聊天历史</span>
        </div>
        <div class="chat-list">
          <div v-for="chat in chatHistories" :key="chat.id"
            :class="['chat-item', { 'active': currentChatId === chat.id }]" @click="selectChat(chat.id)">
            <div class="chat-info">
              <div class="chat-title">{{ chat.title }}</div>
              <div class="chat-date">{{ formatDate(chat.updatedAt) }}</div>
            </div>
            <button class="delete-chat" @click="deleteChat(chat.id, $event)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 6h18M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                <line x1="10" y1="11" x2="10" y2="17"></line>
                <line x1="14" y1="11" x2="14" y2="17"></line>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showSettings" class="settings-overlay" @click.self="closeSettings">
      <div class="settings-modal">
        <div class="settings-header">
          <h3>设置</h3>
          <button class="close-btn" @click="closeSettings">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div class="settings-content">
          <div class="setting-group">
            <label class="setting-label">API URL</label>
            <input v-model="settings.apiUrl" type="text" class="setting-input" placeholder="请输入API地址" />
          </div>

          <div class="setting-group">
            <label class="setting-label">API Key</label>
            <input v-model="settings.apiKey" type="password" class="setting-input" placeholder="请输入API密钥" />
          </div>

          <div class="setting-group">
            <label class="setting-label">模型选择</label>
            <select v-model="settings.modelName" class="setting-select">
              <option v-for="model in modelOptions" :key="model.value" :value="model.value">
                {{ model.label }}
              </option>
            </select>
          </div>

          <div class="setting-group">
            <label class="setting-label">相似问题个数 (Top N)</label>
            <div class="range-input-container">
              <input v-model.number="settings.topN" type="range" min="1" max="20" class="range-input" />
              <span class="range-value">{{ settings.topN }}</span>
            </div>
          </div>

          <div class="setting-group">
            <label class="setting-label">置信度设置</label>
            <div class="range-input-container">
              <input v-model.number="settings.confidence" type="range" min="0" max="1" step="0.01"
                class="range-input" />
              <span class="range-value">{{ (settings.confidence * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>

        <div class="settings-footer">
          <button class="reset-btn" @click="resetSettings">重置</button>
          <div class="footer-actions">
            <button class="cancel-btn" @click="closeSettings">取消</button>
            <button class="save-btn" @click="saveSettings">保存</button>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-wrapper" :class="{ 'full-width': !showSidebar }">
      <div class="chat-header">
        <button class="toggle-sidebar-btn" @click="toggleSidebar">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>

        <div class="header-center">
        </div>
      </div>

      <div class="chat-container">

        <div class="chat-messages" ref="chatContainer">
          <div v-for="message in messages" :key="message.id" :class="['message', message.type]">
            <div class="message-avatar">
              <div v-if="message.type === 'user'" class="user-avatar">U</div>
              <div v-else class="ai-avatar">AI</div>
            </div>
            <div class="message-content">
              <div v-if="message.type === 'user' && (message.question || message.table)" class="user-content">
                <div v-if="message.question" class="user-question">
                  <strong>问题：</strong>{{ message.question }}
                </div>
                <div v-if="message.table" class="user-table">
                  <strong>表格：</strong>
                  <div class="table-container">
                    <table class="data-table">
                      <thead>
                        <tr>
                          <th v-for="header in message.table.header" :key="header">{{ header }}</th>
                        </tr>
                      </thead>
                      <tbody v-if="message.table?.rows">
                        <tr v-for="(row, index) in (message.table.rows || []).slice(0, 5)" :key="index">
                          <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td>
                        </tr>
                        <tr v-if="(message.table.rows || []).length > 5">
                          <td :colspan="(message.table.header || []).length" class="more-rows">
                            ... 还有 {{ message.table.rows.length - 5 }} 行数据
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <div v-if="message.type === 'assistant' && (message.processingSteps?.length || 0) > 0"
                class="processing-steps-container">
                <!-- Intermediate steps (collapsible) -->
                <details
                  v-if="(message.processingSteps?.length || 0) > 1 || (message.processingSteps?.[0]?.step !== 'final' && message.processingSteps?.[0]?.step !== 'end')"
                  class="steps-details" :open="message.isProcessing">
                  <summary class="steps-summary">
                    <span class="summary-title">分析过程</span>
                    <span v-if="message.isProcessing" class="processing-spinner"></span>
                  </summary>
                  <div class="processing-steps">
                    <div v-for="(step, index) in (message.processingSteps?.slice(0, -1) || [])" :key="index"
                      class="processing-step">
                      <div class="step-header">
                        <span class="step-icon" :class="getStepIconClass(step.step)">
                          <svg v-if="step.step === 'start'" width="14" height="14" viewBox="0 0 24 24"
                            fill="currentColor">
                            <path d="M8 5v14l11-7z" />
                          </svg>
                          <svg
                            v-else-if="step.step === 'rag' || step.step === 'rag_done' || step.step === 'similar_search'"
                            width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                            <circle cx="11" cy="11" r="8"></circle>
                            <path d="m21 21-4.35-4.35"></path>
                          </svg>
                          <svg v-else-if="step.step === 'thinking' || step.step === 'answering'" width="14" height="14"
                            viewBox="0 0 24 24" fill="currentColor">
                            <path d="M9 12l2 2 4-4"></path>
                            <circle cx="12" cy="12" r="10"></circle>
                          </svg>
                          <svg v-else-if="step.tool === 'think'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M9.5 2C11.5 2 13 3.5 13 5.5s-1.5 3.5-3.5 3.5S6 7.5 6 5.5 7.5 2 9.5 2z" />
                            <path d="M14.5 2c2 0 3.5 1.5 3.5 3.5s-1.5 3.5-3.5 3.5S11 7.5 11 5.5 12.5 2 14.5 2z" />
                            <path d="M12 9c-2 0-3.5 1.5-3.5 3.5S10 16 12 16s3.5-1.5 3.5-3.5S14 9 12 9z" />
                            <path d="M12 16v5" />
                            <path d="M9 22h6" />
                          </svg>
                          <svg v-else-if="step.step === 'tool_call' || step.step === 'tool_result'" width="14"
                            height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path
                              d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                          </svg>
                          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                            <circle cx="12" cy="12" r="10"></circle>
                          </svg>
                        </span>
                        <span class="step-name">{{ getStepName(step.step) }}</span>
                      </div>
                      <div v-if="step.message" class="step-message">{{ step.message }}</div>
                    </div>
                  </div>
                </details>

                <!-- Current activity status (only visible when processing) -->
                <div v-if="message.isProcessing" class="latest-step">
                   <div v-if="message.status" class="active-step">
                      <span class="active-step-icon">
                        <span class="pulse"></span>
                      </span>
                      {{ message.status }}
                   </div>
                </div>
              </div>

              <div v-if="message.files && message.files.length > 0" class="message-files">
                <div v-for="file in message.files" :key="file.id" class="file-item">
                  <div class="file-icon">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                      <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                  </div>
                  <div class="file-info">
                    <div class="file-name">{{ file.name }}</div>
                    <div class="file-size">{{ formatFileSize(file.size) }}</div>
                  </div>
                </div>
              </div>

              <div v-if="message.generatedImage" class="generated-image">
                <div class="image-container">
                  <img :src="message.generatedImage" alt="Generated Chart" class="chart-image" @load="onImageLoad"
                    @error="onImageError" />
                </div>
              </div>


              <div v-if="message.error" class="message-error-box">
                <div class="error-header">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                  </svg>
                  <span>处理出错</span>
                </div>
                <div class="error-content">{{ message.error }}</div>
              </div>

              <div v-if="message.type === 'assistant' ? (message.content || (message.isProcessing && !message.status)) : !(message.question || message.table)" class="message-text">
                <template v-if="message.type === 'assistant'">
                  <div v-if="message.content">
                    <details v-if="extractReasoning(message.content)" class="reasoning-details">
                      <summary class="reasoning-summary">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                          stroke-width="2">
                          <path d="M9 12l2 2 4-4"></path>
                          <circle cx="12" cy="12" r="10"></circle>
                        </svg>
                        思考过程
                      </summary>
                      <div class="reasoning-content">{{ extractReasoning(message.content) }}</div>
                    </details>
                    <div class="final-answer-content">{{ formatFinalAnswer(message.content) || '分析完成' }}</div>
                    
                    <div v-if="message.reportSummary" class="report-summary-box" style="margin-top: 12px; padding: 12px; background: #f8fafc; border-left: 4px solid #3b82f6; border-radius: 6px; font-size: 0.95em;">
                      <strong style="color: #1e293b; display: flex; align-items: center; gap: 6px;">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                        研报执行摘要
                      </strong>
                      <div style="white-space: pre-wrap; margin-top: 8px; color: #334155; line-height: 1.5;">{{ message.reportSummary }}</div>
                      <a v-if="message.reportUrl" :href="message.reportUrl" target="_blank" style="display: inline-flex; align-items: center; gap: 6px; margin-top: 12px; color: #ffffff; background: #3b82f6; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-weight: 500; font-size: 0.9em; transition: background 0.2s;" onmouseover="this.style.background='#2563eb'" onmouseout="this.style.background='#3b82f6'">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                        下载完整 Word 报告
                      </a>
                    </div>
                  </div>
                  <div v-else-if="message.isProcessing && !message.status" class="typing-placeholder">
                    <span>正在思考...</span>
                  </div>
                </template>
                <template v-else>
                  {{ message.content }}
                </template>
              </div>
              <div class="message-time">{{ formatTime(message.timestamp) }}</div>
            </div>
          </div>

          <div v-if="isLoading" class="message assistant">
            <div class="message-avatar">
              <div class="ai-avatar">AI</div>
            </div>
            <div class="message-content">
              <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        </div>

        <div class="chat-input">
          <div v-if="selectedFiles.length > 0" class="selected-files">
            <div v-for="file in selectedFiles" :key="file.id" class="selected-file">
              <div class="file-preview" :class="{ 'json-file': isJsonFile(file), 'processing': isLoading }">
                <div class="file-icon">
                  <svg v-if="isJsonFile(file)" viewBox="0 0 24 24" width="20" height="20">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="#3b82f6" />
                    <polyline points="14 2 14 8 20 8" fill="none" stroke="#3b82f6" stroke-width="2" />
                    <text x="12" y="16" text-anchor="middle" font-size="6" fill="white" font-weight="bold">JSON</text>
                  </svg>
                  <svg v-else-if="isCsvFile(file)" viewBox="0 0 24 24" width="20" height="20">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="#10b981" />
                    <polyline points="14 2 14 8 20 8" fill="none" stroke="#10b981" stroke-width="2" />
                    <text x="12" y="16" text-anchor="middle" font-size="6" fill="white" font-weight="bold">CSV</text>
                  </svg>
                  <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="#94a3b8">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                </div>
                <div class="file-details">
                  <span class="file-name" :title="file.name">{{ file.name }}</span>
                  <div class="file-info">
                    <span class="file-size">{{ formatFileSize(file.size) }}</span>
                    <span v-if="isJsonFile(file) || isCsvFile(file)" class="json-badge">✓ 已解析</span>
                  </div>
                </div>
                <button class="remove-file" @click="removeFile(file.id)" title="移除文件">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>
            </div>
          </div>

          <div class="input-container">
            <div class="input-wrapper">
              <div class="textarea-container">
                <textarea v-model="inputMessage" @keydown="handleKeydown" placeholder='请输入你的问题，然后点击上传按钮上传包含表格数据的JSON文件

使用方式：
- 单文件上传：点击上传按钮，选择一个JSON文件
- 多文件拼接：点击上传按钮，按住Ctrl键选择多个JSON文件，系统会自动按表头拼接

示例：
1. 输入问题：哪个城市的人口最多？
2. 上传JSON文件，文件内容格式：
{
  "header": ["城市", "人口(万)"],
  "rows": [["北京", "2154"], ["上海", "2428"]]
}' rows="1" :disabled="isLoading"></textarea>
              </div>
              <div class="buttons-container">
                <div class="left-buttons">
                  <button class="action-button add-button" @click="triggerFileUpload" title="上传JSON文件（支持单个或多个文件拼接）">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path
                        d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66L9.64 16.2a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                    </svg>
                  </button>
                  <button class="action-button graph-button" :class="{ 'active': graph_flag }" @click="toggleGraphFlag"
                    title="生成图表">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <line x1="18" y1="20" x2="18" y2="10"></line>
                      <line x1="12" y1="20" x2="12" y2="4"></line>
                      <line x1="6" y1="20" x2="6" y2="14"></line>
                    </svg>
                  </button>
                  <button class="action-button report-button"
                    :class="{ 'disabled': !latestSessionId || isGeneratingReport }" @click="generateReport" title="生成报告"
                    :disabled="!latestSessionId || isGeneratingReport">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                      <polyline points="14,2 14,8 20,8"></polyline>
                      <line x1="16" y1="13" x2="8" y2="13"></line>
                      <line x1="16" y1="17" x2="8" y2="17"></line>
                      <polyline points="10,9 9,9 8,9"></polyline>
                    </svg>
                  </button>
                  <input type="file" ref="fileInput" @change="handleFileSelect"
                    accept=".json,application/json,.csv,text/csv" multiple style="display: none" />

                </div>
                <div class="right-buttons">
                  <button @click="sendMessage" :disabled="isSendDisabled" class="send-button">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
body {
  margin: 0;
  overflow-y: hidden;
}


.settings-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.settings-modal {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  width: 500px;
  max-width: 90vw;
  max-height: 80vh;
  overflow-y: auto;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-20px) scale(0.95);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
}

.settings-header h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #1f2937;
}

.close-btn {
  background: transparent;
  border: none;
  color: #6b7280;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #f3f4f6;
  color: #374151;
}

.settings-content {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.setting-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.setting-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  margin-bottom: 0.25rem;
}

.setting-input {
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 0.875rem;
  transition: all 0.2s;
  background: white;
}

.setting-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.setting-select {
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 0.875rem;
  transition: all 0.2s;
  background: white;
  cursor: pointer;
}

.setting-select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.range-input-container {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.range-input {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: #e5e7eb;
  outline: none;
  cursor: pointer;
}

.range-input::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #3b82f6;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: all 0.2s;
}

.range-input::-webkit-slider-thumb:hover {
  background: #2563eb;
  transform: scale(1.1);
}

.range-input::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #3b82f6;
  cursor: pointer;
  border: none;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.range-value {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  min-width: 40px;
  text-align: center;
  background: #f3f4f6;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
}

.settings-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-top: 1px solid #e5e7eb;
  background: #f9fafb;
  border-radius: 0 0 12px 12px;
}

.footer-actions {
  display: flex;
  gap: 0.75rem;
}

.reset-btn {
  background: transparent;
  border: 1px solid #d1d5db;
  color: #6b7280;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
}

.reset-btn:hover {
  background: #f3f4f6;
  border-color: #9ca3af;
}

.cancel-btn {
  background: transparent;
  border: 1px solid #d1d5db;
  color: #374151;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
}

.cancel-btn:hover {
  background: #f3f4f6;
  border-color: #9ca3af;
}

.save-btn {
  background: #3b82f6;
  border: 1px solid #3b82f6;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
}

.save-btn:hover {
  background: #2563eb;
  border-color: #2563eb;
}

.app-container {
  display: flex;
  width: 100%;
  height: 100%;
  overflow: hidden;
  min-height: 0;
  /* Important for flex-child scrolling */
}

@media (max-width: 768px) {
  .sidebar {
    position: absolute;
    z-index: 50;
    height: 100%;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
  }
}

.sidebar {
  width: 260px;
  background: #f8fafc;
  color: #1e293b;
  display: flex;
  flex-direction: column;
  transition: margin-left 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  border-right: 1px solid #e2e8f0;
  flex-shrink: 0;
  z-index: 100;
}

.sidebar-hidden {
  margin-left: -260px;
}

.sidebar-actions {
  padding: 1rem;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.85rem 1rem;
  background: #ffffff;
  color: #0f172a;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.new-chat-btn:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  transform: translateY(-1px);
}

.new-chat-btn:active {
  transform: translateY(0);
}

.new-chat-btn svg {
  stroke-width: 2.5;
  transition: transform 0.2s ease;
}

.new-chat-btn:hover svg {
  transform: rotate(90deg);
}

.sidebar-nav {
  display: flex;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #e0e0e0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 1rem;
  background: transparent;
  color: #475569;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  margin-right: 0.5rem;
  transition: all 0.2s;
  font-weight: 500;
}

.nav-item:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.nav-item.active {
  background: #eef2ff;
  color: #4f46e5;
}


.chat-history {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-history-header {
  padding: 0.75rem 1rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: #666;
  border-bottom: 1px solid #e0e0e0;
}

.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 0;
  scrollbar-width: thin;
  scrollbar-color: #c1c1c1 transparent;
}

.chat-list::-webkit-scrollbar {
  width: 4px;
}

.chat-list::-webkit-scrollbar-track {
  background: transparent;
}

.chat-list::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 2px;
}

.chat-list::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

.chat-item {
  display: flex;
  align-items: center;
  padding: 0.85rem 1rem;
  margin: 0.25rem 0.65rem;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  justify-content: space-between;
  border: 1px solid transparent;
}

.chat-item:hover {
  background: #f1f5f9;
}

.chat-item.active {
  background: #ffffff;
  color: #4f46e5;
  border-color: #e2e8f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.chat-info {
  flex: 1;
  min-width: 0;
}

.chat-title {
  font-size: 0.85rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 0.25rem;
}

.chat-date {
  font-size: 0.75rem;
  color: #666;
}

.chat-item.active .chat-date {
  color: #0d8f6b;
}

.delete-chat {
  background: transparent;
  border: none;
  color: #999;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.2s;
  margin-left: 0.5rem;
}

.chat-item:hover .delete-chat {
  opacity: 1;
}

.delete-chat:hover {
  background: #f0f0f0;
  color: #ef4444;
}


.chat-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  transition: margin-left 0.3s ease;
  overflow: hidden;
  height: 100%;
  min-height: 0;
}

.full-width {
  margin-left: 0;
}

.chat-container {
  display: flex;
  flex: 1;
  flex-direction: column;
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
  overflow: hidden;
  height: 100%;
  min-height: 0;
  position: relative;
  background: transparent;
}

.chat-header {
  background: transparent;
  padding: 1rem 2rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: flex-start;
  margin-left: 1rem;
}


.visualization-dropdown {
  position: relative;
  z-index: 100;
}

.visualization-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: #f7f7f8;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 0.5rem 1rem;
  font-size: 0.9rem;
  color: #333;
  cursor: pointer;
  transition: all 0.2s ease;
  font-weight: 500;
}

.visualization-btn:hover {
  background: #f0f0f0;
  border-color: #d0d0d0;
}

.visualization-btn svg:last-child {
  transition: transform 0.2s ease;
}

.visualization-btn:hover svg:last-child {
  transform: rotate(180deg);
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  min-width: 180px;
  overflow: hidden;
  animation: dropdownSlideIn 0.2s ease-out;
}

@keyframes dropdownSlideIn {
  from {
    opacity: 0;
    transform: translateY(-8px) scale(0.95);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.75rem 1rem;
  background: transparent;
  border: none;
  color: #333;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background-color 0.2s ease;
  text-align: left;
}

.dropdown-item:hover {
  background: #f7f7f8;
}

.dropdown-item:not(:last-child) {
  border-bottom: 1px solid #f0f0f0;
}

.dropdown-item svg {
  color: #6b7280;
  flex-shrink: 0;
}

.dropdown-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 50;
  background: transparent;
}

.toggle-sidebar-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.5rem;
  margin-right: 1rem;
  color: #6e6e80;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 1rem 2rem 1rem;
  /* More padding at bottom for separation */
  scroll-behavior: smooth;
  scrollbar-width: none;
  -ms-overflow-style: none;
  min-height: 0;
}


.chat-messages::-webkit-scrollbar {
  width: 0;
  background: transparent;
  display: none;
}


.chat-messages::-webkit-scrollbar-track,
.chat-list::-webkit-scrollbar-track {
  display: none;
}

.chat-messages::-webkit-scrollbar-thumb,
.chat-list::-webkit-scrollbar-thumb {
  display: none;
}

.chat-messages::-webkit-scrollbar-thumb:hover,
.chat-list::-webkit-scrollbar-thumb:hover {
  display: none;
}

.message {
  display: flex;
  margin-bottom: 1.5rem;
  animation: fadeIn 0.3s ease-in;
}

.message.user {
  flex-direction: row-reverse;
  justify-content: flex-start;
}

.message-avatar {
  margin: 0 0.75rem;
  flex-shrink: 0;
}

.user-avatar,
.ai-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 0.8rem;
  color: white;
}

.user-avatar {
  background: #e6e9ec;
  color: #333;
}

.ai-avatar {
  background: #eaedf0;
  color: #333;
}

.message-content {
  max-width: 70%;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.message.user .message-content {
  align-items: flex-end;
}

.message-text {
  background: transparent;
  padding: 0.85rem 1.15rem;
  border-radius: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  word-wrap: break-word;
  line-height: 1.6;
  width: fit-content;
  max-width: 100%;
  font-size: 0.95rem;
  color: var(--text-primary);
  border: 1px solid var(--border-light);
}

.message.user .message-text {
  background: var(--primary-color);
  color: white;
  border: none;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
}

.message.assistant .message-text {
  background: #ffffff;
}

.message-time {
  font-size: 0.75rem;
  color: #8e8ea0;
  margin-top: 0.25rem;
  padding: 0 0.5rem;
}


.message-files {
  margin-bottom: 0.5rem;
  width: fit-content;
  max-width: 100%;
}

.file-item {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 8px;
  padding: 0.5rem;
  margin-bottom: 0.5rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.message.user .file-item {
  background: rgba(238, 242, 245, 0.9);
  color: #333;
}


.generated-image {
  margin: 12px 0;
  max-width: 100%;
}

.image-container {
  max-width: 100%;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  background: #fff;
  border: 1px solid #e1e5e9;
}

.chart-image {
  width: 100%;
  height: auto;
  display: block;
  max-width: 600px;
  transition: transform 0.2s ease;
}

.chart-image:hover {
  transform: scale(1.02);
}

.message-status-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding: 6px 10px;
  background: rgba(99, 102, 241, 0.05);
  border-radius: 6px;
  font-size: 0.85rem;
  color: #6366f1;
  border: 1px solid rgba(99, 102, 241, 0.1);
}

.status-dot {
  width: 8px;
  height: 8px;
  background-color: #6366f1;
  border-radius: 50%;
  animation: status-pulse 1.5s infinite;
}

@keyframes status-pulse {
  0% { transform: scale(0.9); opacity: 0.6; }
  50% { transform: scale(1.1); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.6; }
}

.status-text {
  font-weight: 500;
}

.message-error-box {
  margin-bottom: 12px;
  padding: 10px;
  background: #fff5f5;
  border: 1px solid #feb2b2;
  border-radius: 8px;
  color: #c53030;
}

.error-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: bold;
  font-size: 0.85rem;
  margin-bottom: 4px;
}

.error-content {
  font-size: 0.85rem;
  line-height: 1.4;
}

.typing-placeholder {
  color: #94a3b8;
  font-style: italic;
  font-size: 0.9rem;
  padding: 4px 0;
}

.final-answer-content {
  font-size: 1rem;
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.reasoning-details {
  margin-bottom: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.file-icon {
  margin-right: 0.5rem;
  color: #6e6e80;
}

.message.user .file-icon {
  color: #333;
}

.file-info {
  flex: 1;
}

.file-name {
  font-size: 0.9rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.file-size {
  font-size: 0.75rem;
  color: #8e8ea0;
}

.message.user .file-size {
  color: #666;
}

.typing-indicator {
  background: transparent;
  padding: 1rem;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  gap: 0.25rem;
  width: fit-content;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #8e8ea0;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

.chat-input {
  width: 100%;
  padding: 0 1rem 24px 1rem;
  /* Margin from bottom */
  background: transparent;
  flex-shrink: 0;
  box-sizing: border-box;
}

.input-container {
  position: relative;
  width: 100%;
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-radius: 24px;
  padding: 8px 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12);
  /* Prominent floating shadow */
  border: 1px solid var(--border-color);
  width: 100%;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}

.input-wrapper:focus-within {
  border-color: var(--primary-color);
  box-shadow: 0 16px 48px rgba(99, 102, 241, 0.15);
}

.textarea-container {
  width: 100%;
}

.buttons-container {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
}

.left-buttons {
  display: flex;
  align-items: center;
}

.right-buttons {
  display: flex;
  align-items: center;
}

.action-button {
  background: transparent;
  border: none;
  color: #70757a;
  cursor: pointer;
  padding: 8px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
  flex-shrink: 0;
}

.add-button {
  color: #444;
}

.graph-button {
  color: #70757a;
  margin-left: 8px;
}

.graph-button.active {
  background-color: #4285f4;
  color: white;
}

.graph-button.active:hover {
  background-color: #3367d6;
}

.report-button {
  color: #70757a;
  margin-left: 8px;
}

.report-button.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.report-button:not(.disabled):hover {
  background-color: #f0f0f0;
  color: #2a9d8f;
}

.action-button:hover {
  background-color: #f0f0f0;
}

textarea {
  width: 100%;
  min-height: 44px;
  max-height: 200px;
  padding: 8px 12px;
  border: none;
  resize: none;
  font-family: inherit;
  font-size: 1rem;
  line-height: 1.5;
  color: var(--text-primary);
  background: transparent;
  outline: none;
  overflow-y: auto;
}

textarea:focus {
  outline: none;
  box-shadow: none;
}

textarea:disabled {
  background: transparent;
  color: #8e8ea0;
}

.send-button {
  background: var(--primary-color);
  color: white;
  border: none;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(99, 102, 241, 0.3);
}

.send-button:hover:not(:disabled) {
  background: var(--primary-hover);
  transform: scale(1.05);
}

.send-button:disabled {
  background: #e2e8f0;
  color: #94a3b8;
  box-shadow: none;
  cursor: not-allowed;
}


.selected-files {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
  max-width: 100%;
}

.selected-file {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f8fafc;
  border-radius: 8px;
  padding: 0.75rem;
  border: 1px solid #e2e8f0;
  transition: all 0.2s ease;
  width: 100%;
}

.selected-file:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.file-preview {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  min-width: 0;
}

.file-preview.processing {
  opacity: 0.7;
}

.file-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
  border-radius: 6px;
  flex-shrink: 0;
}

.file-details {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
  min-width: 0;
}

.file-name {
  font-weight: 500;
  color: #1e293b;
  font-size: 0.875rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: #64748b;
}

.file-size {
  color: #64748b;
}

.json-badge {
  background: #dcfce7;
  color: #16a34a;
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
  font-weight: 500;
  font-size: 0.625rem;
}

.remove-file {
  background: transparent;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  padding: 0.375rem;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.remove-file:hover {
  background: #fee2e2;
  color: #dc2626;
}



.remove-file:hover {
  color: #ef4444;
}

.input-footer {
  display: none;
}

.input-hint {
  font-size: 0.75rem;
  color: #8e8ea0;
  margin: 0;
}


.user-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-width: 100%;
  overflow-x: hidden;
}

.user-question {
  background: rgba(238, 242, 245, 0.8);
  padding: 0.75rem;
  border-radius: 8px;
  font-size: 0.9rem;
  line-height: 1.4;
}

.user-table {
  background: rgba(238, 242, 245, 0.8);
  padding: 0.75rem;
  border-radius: 8px;
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

.table-container {
  margin-top: 0.5rem;
  overflow-x: auto;
  border-radius: 6px;
  border: 1px solid #e0e0e0;
  max-width: 100%;
  -webkit-overflow-scrolling: touch;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
  background: white;
}

.data-table th,
.data-table td {
  padding: 0.5rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid #f0f0f0;
}

.data-table th {
  background: #f8f9fa;
  font-weight: 500;
  color: #333;
}

.data-table tbody tr:hover {
  background: #f8f9fa;
}

.more-rows {
  text-align: center;
  color: #666;
  font-style: italic;
  background: #f8f9fa;
}


.processing-steps {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.processing-step {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 8px;
  padding: 0.75rem;
  border-left: 3px solid #e0e0e0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.step-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.step-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 0.75rem;
  font-weight: bold;
}

.step-icon-start {
  background: #e3f2fd;
  color: #1976d2;
}

.step-icon-search {
  background: #f3e5f5;
  color: #7b1fa2;
}

.step-icon-processing {
  background: #fff3e0;
  color: #f57c00;
}

.step-icon-final {
  background: #e8f5e8;
  color: #388e3c;
}

.step-icon-complete {
  background: #e8f5e8;
  color: #388e3c;
}

.step-icon-default {
  background: #f5f5f5;
  color: #666;
}

.step-name {
  font-weight: 500;
  color: #333;
  flex: 1;
}

.step-time {
  font-size: 0.75rem;
  color: #666;
}

.step-message {
  color: #555;
  font-size: 0.9rem;
  margin: 0.25rem 0;
}


.similar-questions {
  margin-top: 0.5rem;
}

.similar-header {
  font-size: 0.85rem;
  color: #666;
  margin-bottom: 0.25rem;
}

.similar-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.similar-id {
  background: #f0f0f0;
  color: #555;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-family: monospace;
}


.answer-result {
  margin-top: 0.5rem;
}

.result-stats {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.stat-item {
  background: #f8f9fa;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  color: #555;
}


.final-result {
  margin-top: 0.5rem;
  padding: 0.75rem;
  background: #e8f5e8;
  border-radius: 6px;
  border-left: 3px solid #4caf50;
}

.final-answer {
  font-weight: 500;
  color: #2e7d32;
  margin-bottom: 0.25rem;
  font-size: 0.95rem;
}

.guidance-confidence {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: #fff3cd;
  border-radius: 6px;
  border-left: 3px solid #ffc107;
  margin-top: 0.5rem;
}

.confidence-label {
  font-weight: 500;
  color: #856404;
  font-size: 0.875rem;
}

.confidence-value {
  font-weight: 600;
  color: #b45309;
  font-size: 0.875rem;
  background: #fef3c7;
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
}

.context-info {
  font-size: 0.75rem;
  color: #666;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes typing {

  0%,
  60%,
  100% {
    transform: scale(1);
    opacity: 0.5;
  }

  30% {
    transform: scale(1.2);
    opacity: 1;
  }
}



.file-details {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
  min-width: 0;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
}

.json-badge {
  background: #f39c12;
  color: white;
  padding: 0.125rem 0.375rem;
  border-radius: 10px;
  font-size: 0.625rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.025em;
}

.file-size {
  color: #666;
}

.file-type {
  color: #666;
  font-size: 0.7rem;
}

/* Agent Visualization Styles */
.agent-tool-info {
  margin: 0.5rem 0;
  padding: 0.5rem 0.75rem;
  background: #f1f5f9;
  border-left: 3px solid #6366f1;
  border-radius: 4px 8px 8px 4px;
}

.tool-badge {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #4f46e5;
  margin-bottom: 0.25rem;
}

.tool-icon {
  font-size: 0.9rem;
}

.tool-summary {
  font-family: monospace;
  font-size: 0.75rem;
  color: #475569;
  background: white;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
  display: inline-block;
}

.think-tool-info {
  background: #fdf2f8;
  border-left: 3px solid #db2777;
}

.think-tool-info .tool-badge {
  color: #be185d;
}

.think-reasoning {
  font-size: 0.85rem;
  color: #374151;
  background: white;
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid #f9a8d4;
  line-height: 1.5;
  white-space: pre-wrap;
  margin-top: 0.5rem;
}

.think-confidence {
  margin-top: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px dashed #f9a8d4;
  font-size: 0.8rem;
  color: #9d174d;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.think-confidence strong {
  font-size: 1rem;
  color: #db2777;
}

.step-icon-think {
  background: #fdf2f8;
  color: #db2777;
}

.error-details {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: #fef2f2;
  border-left: 3px solid #ef4444;
  color: #b91c1c;
  font-size: 0.8rem;
  border-radius: 4px;
}

.similar-id-container {
  display: inline-flex;
  align-items: center;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
}

.similar-id {
  background: transparent;
  color: #334155;
  padding: 0.2rem 0.5rem;
  font-size: 0.75rem;
  font-family: inherit;
}

.similarity-score {
  font-size: 0.7rem;
  background: #e0e7ff;
  color: #4338ca;
  padding: 0.2rem 0.4rem;
  border-left: 1px solid #c7d2fe;
}

.agent-confidence {
  display: inline-flex;
  align-items: center;
  margin-top: 0.5rem;
  padding: 0.35rem 0.65rem;
  background: #f0fdf4;
  color: #166534;
  border: 1px solid #bbf7d0;
  border-radius: 6px;
  font-size: 0.8rem;
}

.step-icon-tool {
  background: #eef2ff;
  color: #6366f1;
}

.step-icon-tool-result {
  background: #f0fdf4;
  color: #10b981;
}

.step-icon-error {
  background: #fef2f2;
  color: #ef4444;
}

.reasoning-details {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 0.75rem;
  overflow: hidden;
}

.reasoning-summary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  user-select: none;
  background: #f1f5f9;
  transition: background 0.2s;
}

.reasoning-summary:hover {
  background: #e2e8f0;
}

.reasoning-content {
  padding: 0.75rem;
  font-size: 0.85rem;
  color: #475569;
  border-top: 1px solid #e2e8f0;
  white-space: pre-wrap;
  background: #ffffff;
}

.final-answer-content {
  white-space: pre-wrap;
}

.steps-details {
  border: 1px solid #eef2f6;
  border-radius: 12px;
  background: #fcfdfe;
  margin-bottom: 0.75rem;
  overflow: hidden;
  transition: all 0.3s ease;
}

.steps-summary {
  list-style: none;
  padding: 0.6rem 1rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: #5c6b8a;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f1f5f9;
  user-select: none;
}

.steps-summary::-webkit-details-marker {
  display: none;
}

.steps-summary:hover {
  background: #e2e8f0;
}

.summary-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.summary-title::before {
  content: "▹";
  transition: transform 0.2s;
  display: inline-block;
}

.steps-details[open] .summary-title::before {
  transform: rotate(90deg);
}

.processing-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(99, 102, 241, 0.1);
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.active-step {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: #f0f7ff;
  border: 1px solid #d0e4ff;
  border-radius: 10px;
  font-size: 0.9rem;
  color: #0056b3;
  margin-bottom: 0.5rem;
}

.active-step-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.pulse {
  display: inline-block;
  width: 8px;
  height: 8px;
  background: #3b82f6;
  border-radius: 50%;
  box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7);
  }

  70% {
    transform: scale(1);
    box-shadow: 0 0 0 10px rgba(59, 130, 246, 0);
  }

  100% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.latest-step {
  margin-top: 0.5rem;
}

.final-result {
  margin-top: 0.5rem;
  padding: 1.25rem;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

.final-answer {
  font-size: 1.05rem;
  line-height: 1.6;
  color: #1e293b;
  font-weight: 500;
}

.active-step.completed-step {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.active-step.completed-step .active-step-icon {
  background: #22c55e;
  box-shadow: 0 0 10px rgba(34, 197, 94, 0.3);
}

/* RAG Results Styling */
.rag-results-container {
  margin-top: 10px;
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid #e2e8f0;
}

.rag-results-header {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
}

.rag-results-header::before {
  content: "";
  display: inline-block;
  width: 3px;
  height: 12px;
  background: #3b82f6;
  margin-right: 6px;
  border-radius: 2px;
}

.rag-results-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rag-item-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px;
  transition: all 0.2s ease;
}

.rag-item-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  transform: translateY(-1px);
}

.rag-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.rag-id {
  font-size: 11px;
  font-family: monospace;
  color: #64748b;
  background: #f1f5f9;
  padding: 1px 4px;
  border-radius: 4px;
}

.rag-score {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 10px;
}

.score-high {
  background: #dcfce7;
  color: #166534;
}

.score-medium {
  background: #fef9c3;
  color: #854d0e;
}

.score-low {
  background: #f1f5f9;
  color: #475569;
}

.rag-card-body {
  font-size: 13px;
  color: #334155;
  line-height: 1.5;
}

/* Sidebar User Styling */
.sidebar-user {
  padding: 12px;
  margin: 12px;
  background: #f8fafc;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid #e2e8f0;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  overflow: hidden;
}

.user-avatar {
  width: 32px;
  height: 32px;
  background: #3b82f6;
  color: white;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  flex-shrink: 0;
}

.username {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.logout-btn {
  background: none;
  border: none;
  color: #64748b;
  padding: 6px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logout-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}
</style>