 <template>
  <div class="kv-root">
    <div class="kv-header">
      <span class="kv-title">知识可视化大屏</span>
      
      <div class="kv-dropdown" ref="dropdownRef">
        <button class="kv-dropdown-btn" @click="toggleDropdown">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M12 1v6m0 6v6"></path>
            <path d="m21 12-6-6-6 6-6-6"></path>
          </svg>
          更多选项
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" 
               :class="{ 'rotate': showDropdown }">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>
        
        <div v-show="showDropdown" class="kv-dropdown-menu">
          <div class="kv-dropdown-item" @click="handleQuizClick">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2h-4"></path>
              <polyline points="6,9 12,15 18,9"></polyline>
            </svg>
            答题界面
          </div>
          
          <div class="kv-dropdown-item" @click="handleTeachingClick">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 10v6M2 10l10-5 10 5-10 5z"></path>
              <path d="M6 12v5c3 3 9 3 12 0v-5"></path>
            </svg>
            教学可视化
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="showDropdown" class="kv-dropdown-overlay" @click="closeDropdown"></div>
    
    <div class="kv-content">
      <div class="kv-sidebar">
        <div class="kv-search-bar">
          <input
            v-model="searchKeyword"
            placeholder="请输入关键字搜索问题..."
            class="kv-search-input"
            @keyup.enter="handleSearch"
            :disabled="loading"
          />
          <select 
            v-model="pageSize" 
            class="kv-page-size-select" 
            @change="changePageSize(pageSize)"
            :disabled="loading"
          >
            <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}条/页</option>
          </select>
        </div>
        
        <div class="kv-page-list">
          <div v-if="loading" class="kv-loading">
            <div class="kv-loading-spinner"></div>
            <span>{{ searchKeyword ? '搜索中...' : '加载中...' }}</span>
          </div>
          
        <div v-else-if="pageData.length > 0">
          <div 
            v-for="item in pageData" 
            :key="item.id" 
            class="kv-page-item"
            :class="{ 
              'kv-page-item-clicking': clickingQuestionId === item.id,
              'kv-page-item-clickable': clickingQuestionId !== item.id 
            }"
            @click="handleQuestionClick(item)"
            :style="{ 
              cursor: clickingQuestionId === item.id ? 'wait' : 'pointer' 
            }"
          >
            <div class="kv-page-item-content">
              <div class="kv-page-item-title">{{ item.name }}</div>
              <div class="kv-page-item-desc" :title="item.desc">{{ item.desc }}</div>
              <div class="kv-page-item-id">ID: {{ item.id }}</div>
            </div>
            
            <div v-if="clickingQuestionId === item.id" class="kv-page-item-loading">
              <div class="kv-page-item-spinner"></div>
              <span>分析中...</span>
            </div>
          </div>
        </div>
          
          <div v-else class="kv-no-data">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.35-4.35"></path>
            </svg>
            <span>{{ searchKeyword ? '未找到相关问题' : '暂无数据' }}</span>
          </div>
        </div>
        
        <div class="kv-pagination">
          <button 
            :disabled="currentPage === 1 || loading" 
            @click="goToPrevPage"
          >
            上一页
          </button>
          <span>
            第 {{ currentPage }} / {{ Math.max(1, Math.ceil(total / pageSize)) }} 页
            <br>
            <small>共 {{ total }} 条</small>
          </span>
          <button 
            :disabled="currentPage >= Math.ceil(total / pageSize) || total === 0 || loading" 
            @click="goToNextPage"
          >
            下一页
          </button>
        </div>
      </div>
      <div class="kv-main-chart">
        <div class="kv-main-chart-title">知识图谱展示</div>
        
        <div v-if="showDetailView && questionDetail" class="kv-detail-view">
          <div class="kv-detail-header">
            <h2 class="kv-detail-title">问题详细信息</h2>
            <button class="kv-return-btn" @click="returnToGraphView">
              ← 返回关系图
            </button>
          </div>
          
          <div class="kv-detail-section">
            <div class="kv-detail-field">
              <label class="kv-field-label">问题ID：</label>
              <span class="kv-field-value">{{ questionDetail.id }}</span>
            </div>
            
            <div class="kv-detail-field">
              <label class="kv-field-label">问题内容：</label>
              <span class="kv-field-value">{{ questionDetail.question }}</span>
            </div>
            
            <div class="kv-detail-field">
              <label class="kv-field-label">问题骨架：</label>
              <span class="kv-field-value">{{ questionDetail.question_skeleton }}</span>
            </div>
          </div>
          
          <div class="kv-detail-section">
            <h3 class="kv-section-title">数据表格：</h3>
            <div class="kv-table-container">
              <table class="kv-data-table">
                <thead>
                  <tr>
                    <th v-for="header in questionDetail.table_info.header" :key="header">
                      {{ header.length > 14 ? header.substring(0, 14) + '...' : header }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, rowIndex) in questionDetail.table_info.rows.slice(0, 5)" :key="rowIndex">
                    <template v-for="(cell, cellIndex) in row" :key="cellIndex">
                      <td v-if="cellIndex < questionDetail.table_info.header.length">
                        {{ String(cell).length > 14 ? String(cell).substring(0, 14) + '...' : String(cell) }}
                      </td>
                    </template>
                  </tr>
                </tbody>
              </table>
              <div v-if="questionDetail.table_info.rows.length > 5" class="kv-table-more">
                ... 还有 {{ questionDetail.table_info.rows.length - 5 }} 行数据
              </div>
            </div>
          </div>
          
          <div class="kv-detail-section">
            <h3 class="kv-section-title">教学策略：</h3>
            <div class="kv-strategy-list">
              <div class="kv-strategy-item">
                <span class="kv-strategy-number">1.</span>
                <span class="kv-strategy-label">COT:</span>
                <span class="kv-strategy-content">
                  {{ questionDetail.strategies.cot }}
                </span>
              </div>
              
              <div class="kv-strategy-item">
                <span class="kv-strategy-number">2.</span>
                <span class="kv-strategy-label">列排序:</span>
                <span class="kv-strategy-content">{{ questionDetail.strategies.column_sorting.join(', ') }}</span>
              </div>
              
              <div class="kv-strategy-item">
                <span class="kv-strategy-number">3.</span>
                <span class="kv-strategy-label">模式链接:</span>
                <span class="kv-strategy-content">
                  {{ questionDetail.strategies.schema_linking }}
                </span>
              </div>
            </div>
          </div>
          
          <div class="kv-detail-section">
            <div class="kv-detail-field">
              <label class="kv-field-label">最终答案：</label>
              <span class="kv-field-value kv-answer">{{ questionDetail.answer.join(', ') }}</span>
            </div>
          </div>
        </div>
        
        <v-chart v-else ref="mainChartRef" class="kv-main-chart-section" :option="option1" autoresize />
      </div>
      <div class="kv-side-charts">

        <div class="kv-side-chart kv-knowledge-stats" style="flex: 1;">
          <div class="kv-chart-wrapper">
            <div class="kv-independent-stats">
              <div class="kv-stat-card">
                <div class="kv-stat-icon learning">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14,2 14,8 20,8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10,9 9,9 8,9"></polyline>
                  </svg>
                </div>
                <div class="kv-stat-info">
                  <div class="kv-stat-label">问题总数</div>
                  <div class="kv-stat-value primary">{{ knowledgeStats.questionCount.toLocaleString() }}</div>
                  <div class="kv-stat-unit">个问题</div>
                </div>
              </div>
              
              <div class="kv-stat-card">
                <div class="kv-stat-icon type">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                    <point cx="12" cy="17" r="1"></point>
                  </svg>
                </div>
                <div class="kv-stat-info">
                  <div class="kv-stat-label">平均问题长度</div>
                  <div class="kv-stat-value warning">{{ knowledgeStats.questionTypeCount }}</div>
                  <div class="kv-stat-unit">字符</div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="kv-side-chart" style="flex: 1;">
          <div class="kv-side-chart-title">策略使用频率</div>
          <v-chart class="kv-side-chart-section" :option="option3" autoresize />
        </div>
        <div class="kv-side-chart kv-wordcloud-chart" style="flex: 1;">
          <div class="kv-side-chart-section kv-wordcloud-container">
            <img 
              src="/wordcloud_spaced.png" 
              alt="词云图" 
              class="kv-wordcloud-image"
              @error="handleWordcloudError"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import { use } from 'echarts/core'
import { GraphicComponent, TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { GraphChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import axios from 'axios'

use([
  GraphicComponent, 
  TitleComponent, 
  TooltipComponent, 
  LegendComponent, 
  GraphChart,
  CanvasRenderer
])


interface Question {
  table_id: string
  question: string
}

interface PageItem {
  id: string
  name: string
  desc: string
  question: string
}

interface PaginationInfo {
  current_page: number
  page_size: number
  total_count: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

interface ApiResponse {
  status: string
  data: {
    questions: Question[]
    pagination: PaginationInfo
  }
}

interface QuestionDetail {
  id: string
  question: string
  question_skeleton: string
  answer: string[]
  strategies: {
    cot: string
    column_sorting: string[]
    schema_linking: string
  }
  table_info: {
    header: string[]
    rows: (string | number)[][]
  }
}

const router = useRouter()

const showDropdown = ref(false)
const dropdownRef = ref()

const toggleDropdown = () => {
  showDropdown.value = !showDropdown.value
}

const closeDropdown = () => {
  showDropdown.value = false
}

const handleQuizClick = () => {
  closeDropdown()
  router.push('/').catch(console.error)
}

const handleTeachingClick = () => {
  closeDropdown()
  router.push('/teaching-visualization').catch(console.error)
}

const handleClickOutside = (event: Event) => {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target as Node)) {
    closeDropdown()
  }
}

const pageData = ref<PageItem[]>([])
const currentPage = ref(1)
const pageSize = ref(8)
const total = ref(0)
const searchKeyword = ref('')
const loading = ref(false)
const pageSizeOptions = [8, 20, 50]

const clickingQuestionId = ref<string | null>(null)

const showDetailView = ref(false)
const questionDetail = ref<QuestionDetail | null>(null)
const loadingDetail = ref(false)
const mainChartRef = ref()
const currentQuestionTableId = ref<string | null>(null)
const previousGraphOption = ref<EChartsOption | null>(null)

const handleQuestionClick = async (item: PageItem) => {
  if (clickingQuestionId.value === item.id) {
    return
  }
  
  clickingQuestionId.value = item.id
  
  try {
    console.log('点击问题:', item.question)
    console.log('问题table_id:', item.id)
    
    currentQuestionTableId.value = item.id
    
    const response = await axios.get('http://127.0.0.1:8000/api/knowledge/similarity-graph', {
      params: {
        question: item.question,
        max_layers: 2,
        top_n: 5
      },
      timeout: 10000
    })
    
    console.log('相似性图谱API返回数据:', response.data)
    
    if (response.data.status === 'success' && response.data.data) {
      updateSimilarityGraph(response.data.data.graph_data)
    } else {
      console.warn('API返回格式异常:', response.data)
      showErrorGraph('数据格式错误')
    }
  
  } catch (error) {
    console.error('获取相似性图谱失败:', error)
    showErrorGraph('网络请求失败')
  } finally {
    setTimeout(() => {
      clickingQuestionId.value = null
    }, 500)
  }
}

const fetchPageData = async (page = 1, size = 7, keyword = '') => {
  loading.value = true
  try {
    const params = {
      page,
      page_size: size,
      ...(keyword && { search: keyword })
    }
    
    const res = await axios.get<ApiResponse>('http://127.0.0.1:8000/api/knowledge/questions', { 
      params,
      timeout: 5000 
    })
    
    if (res.data.status === 'success' && res.data.data) {
      const { questions, pagination } = res.data.data
      
      pageData.value = questions.map((item: Question): PageItem => ({
        id: item.table_id,
        name: `问题 ${item.table_id}`,
        desc: item.question,
        question: item.question
      }))
      
      total.value = pagination.total_count
      currentPage.value = pagination.current_page
    } else {
      console.error('API响应格式错误:', res.data)
      pageData.value = []
      total.value = 0
    }
  } catch (error) {
    console.error('获取分页数据失败:', error)
    pageData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const changePageSize = (newSize: number) => {
  pageSize.value = newSize
  currentPage.value = 1
}

const handleSearch = () => {
  currentPage.value = 1
  fetchPageData(currentPage.value, pageSize.value, searchKeyword.value)
}

watch([currentPage, pageSize], ([page, size]) => {
  fetchPageData(page, size, searchKeyword.value)
}, { immediate: false })

const goToPrevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
  }
}

const goToNextPage = () => {
  const totalPages = Math.ceil(total.value / pageSize.value)
  if (currentPage.value < totalPages) {
    currentPage.value++
  }
}

const fetchQuestionDetail = async (tableId: string) => {
  loadingDetail.value = true
  try {
    console.log('获取问题详细信息:', tableId)
    
    if (option1.value && !showDetailView.value) {
      previousGraphOption.value = JSON.parse(JSON.stringify(option1.value))
      console.log('保存当前关系图配置')
    }
    
    const response = await axios.get(`http://127.0.0.1:8000/api/knowledge/question/${tableId}`, {
      timeout: 10000
    })
    
    console.log('问题详细信息API返回:', response.data)
    
    if (response.data.status === 'success' && response.data.data) {
      questionDetail.value = response.data.data
      showDetailView.value = true
      updateDetailView()
    } else {
      console.error('获取问题详细信息失败:', response.data)
      showErrorGraph('获取问题详细信息失败')
    }
  } catch (error) {
    console.error('获取问题详细信息API调用失败:', error)
    showErrorGraph('网络请求失败')
  } finally {
    loadingDetail.value = false
  }
}

const returnToGraphView = () => {
  showDetailView.value = false
  questionDetail.value = null
  
  if (previousGraphOption.value) {
    option1.value = previousGraphOption.value
    console.log('快速恢复之前的关系图')
    
    setTimeout(() => {
      if (mainChartRef.value && mainChartRef.value.chart) {
        console.log('重新绑定图表点击事件')
        mainChartRef.value.chart.off('click', handleChartClick)
        mainChartRef.value.chart.on('click', handleChartClick)
      }
    }, 100)
  } else {
    option1.value = {
      title: { 
        text: '点击左侧问题查看相似度关系图', 
        left: 'center', 
        textStyle: { fontSize: 16, color: '#999' } 
      },
      graphic: {
        type: 'text',
        left: 'center',
        top: 'center',
        style: {
          text: '👈 点击左侧任意问题\n生成相似度关系图',
          fontSize: 18,
          fill: '#ccc',
          fontWeight: 'normal',
          lineHeight: 30
        }
      },
      backgroundColor: '#fafafa'
    }
  }
}

const handleChartClick = (params: any) => {
  console.log('图表点击事件:', params)
  
  if (params.dataType === 'node' && params.data) {
    const nodeData = params.data
    console.log('点击的节点数据:', nodeData)
    
    let tableId: string | null = null
    
    if (currentQuestionTableId.value && 
        (nodeData.name === '查询问题' || 
         nodeData.category === 0 || 
         nodeData.id === 'query' ||
         params.dataIndex === 0)) {
      tableId = currentQuestionTableId.value
      console.log('使用第一个问题的table_id:', tableId)
    } else {
      tableId = nodeData.id || nodeData.table_id || nodeData.name
      
      if (typeof tableId === 'string' && tableId.includes('-')) {
        const idMatch = tableId.match(/(\w+-\d+)/)
        if (idMatch) {
          tableId = idMatch[1]
        }
      }
    }
    
    console.log('最终提取的table_id:', tableId)
    
    if (tableId) {
      fetchQuestionDetail(tableId)
    } else {
      console.warn('无法获取节点的table_id')
    }
  }
}

const updateDetailView = () => {
  if (!questionDetail.value) return
  
  console.log('问题详细信息已更新，使用 HTML 模板展示')
}

const updateSimilarityGraph = (graphData: any) => {
  try {
    console.log('开始构建相似性关系图，原始数据:', JSON.stringify(graphData, null, 2))

    const graphOption: EChartsOption = {
      title: {
        left: 'center',
        top: '2%',
        textStyle: {
          fontSize: 18,
          fontWeight: 'bold' as any,
          color: '#333'
        },
        subtextStyle: {
          fontSize: 12,
          color: '#666',
          lineHeight: 20
        }
      },
      tooltip: {
        trigger: 'item',
        confine: true,
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#ddd',
        borderWidth: 1,
        textStyle: {
          color: '#333',
          fontSize: 12
        },
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            const isStartNode = params.dataIndex === 0 || 
                               params.data.category === 0 || 
                               params.data.name === '查询问题' ||
                               params.data.id === 'query'
            
            if (isStartNode) {
              return `
                <div style="padding: 8px;">
                  <div style="font-weight: bold; margin-bottom: 4px; color: #1976d2;">起始问题</div>
                  <div style="font-size: 12px; margin-bottom: 4px;">${params.data.name}</div>
                  <div style="font-size: 11px; color: #666;">点击查看详细信息</div>
                  <div style="font-size: 10px; color: #999; margin-top: 4px;">ID: ${params.data.id || 'N/A'}</div>
                </div>
              `
            } else {
              return `
                <div style="padding: 8px;">
                  <div style="font-weight: bold; margin-bottom: 4px; color: #666;">相似问题节点</div>
                  <div style="font-size: 11px; color: #666;">点击查看详细信息</div>
                  <div style="font-size: 10px; color: #999; margin-top: 4px;">ID: ${params.data.id || 'N/A'}</div>
                </div>
              `
            }
          }
          return params.value
        }
      },
      legend: {
        orient: 'horizontal',
        bottom: '2%',
        data: graphData.categories.map((category: any) => category.name || category),
        textStyle: {
          fontSize: 12,
          color: '#666'
        },
        itemGap: 20
      },
      animationDuration: 1500,
      animationEasingUpdate: 'quinticInOut',
      series: [
        {
          name: '问题相似度关系',
          type: 'graph',
          layout: 'force',
          data: graphData.nodes,
          links: graphData.links,
          categories: graphData.categories,
          roam: true,
          focusNodeAdjacency: true,
          draggable: true,
          force: {
            repulsion: 1200,
            gravity: 0.1,
            edgeLength: 200,
            layoutAnimation: true
          },
          label: {
            show: true,
            position: 'right',
            formatter: (params: any) => {
              if (params.dataIndex === 0 || 
                  params.data.category === 0 || 
                  params.data.name === '查询问题' ||
                  params.data.id === 'query') {
                return params.data.name
              }
              return params.data.id || `节点${params.dataIndex + 1}`
            },
            fontSize: 12,
            color: '#333'
          },
          labelLayout: {
            hideOverlap: true
          },
          scaleLimit: {
            min: 0.4,
            max: 2
          },
          lineStyle: {
            color: 'source',
            curveness: 0.3,
            opacity: 0.8
          },
          emphasis: {
            focus: 'adjacency',
            lineStyle: {
              width: 6,
              opacity: 1
            },
            itemStyle: {
              shadowBlur: 20,
              shadowColor: 'rgba(0, 0, 0, 0.3)'
            }
          }
        }
      ]
    }
    option1.value = graphOption
    console.log('相似性关系图更新完成，option1.value 已更新')

    setTimeout(() => {
      console.log('延迟检查: option1.value =', option1.value)
      if (mainChartRef.value && mainChartRef.value.chart) {
        console.log('重新绑定图表点击事件')
        mainChartRef.value.chart.off('click', handleChartClick)
        mainChartRef.value.chart.on('click', handleChartClick)
      }
    }, 100)
    
  } catch (error) {
    console.error('构建相似性关系图失败:', error)
    showErrorGraph('构建图表失败')
  }
}

const showErrorGraph = (errorMsg: string) => {
  option1.value = {
    title: {
      text: '加载失败',
      left: 'center',
      top: 'center',
      textStyle: {
        fontSize: 24,
        color: '#FF6B6B',
        fontWeight: 'bold'
      }
    },
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: '60%',
        style: {
          text: errorMsg,
          fontSize: 16,
          fill: '#999'
        }
      },
      {
        type: 'text',
        left: 'center',
        top: '65%',
        style: {
          text: '请重试或检查网络连接',
          fontSize: 14,
          fill: '#ccc'
        }
      }
    ],
    backgroundColor: '#fafafa'
  }
}


const knowledgeStats = ref({
  questionCount: 0,
  questionTypeCount: 0
})

const option1 = ref<EChartsOption>({
  title: { 
    text: '点击左侧问题查看相似度关系图', 
    left: 'center', 
    textStyle: { fontSize: 16, color: '#999' } 
  },
  graphic: {
    type: 'text',
    left: 'center',
    top: 'center',
    style: {
      text: '👈 点击左侧任意问题\n生成相似度关系图',
      fontSize: 18,
      fill: '#ccc',
      fontWeight: 'normal',
      lineHeight: 30
    }
  },
  backgroundColor: '#fafafa'
})

const option3 = ref<EChartsOption>({
  title: { left: 'center', top: '5%', textStyle: { fontSize: 16 } },
  tooltip: { trigger: 'item', formatter: '{a} <br/>{b}: {c}次 ({d}%)' },
  legend: { orient: 'horizontal', bottom: '2%', textStyle: { fontSize: 11 }, itemGap: 15 },
  series: []
})

const handleWordcloudError = (event: Event) => {
  console.error('词云图片加载失败:', event)
  const img = event.target as HTMLImageElement
  img.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200"><rect width="100%" height="100%" fill="%23f3f4f6"/><text x="50%" y="50%" text-anchor="middle" font-family="Arial" font-size="14" fill="%236b7280">词云图片加载失败</text></svg>'
}

const fetchData = async () => {
  try {
    const [strategyRes, overviewRes] = await Promise.all([
      axios.get('http://127.0.0.1:8000/api/knowledge/strategy-statistics', { timeout: 5000 }),
      axios.get('http://127.0.0.1:8000/api/knowledge/overview', { timeout: 5000 })
    ])

    if (strategyRes.data.status === 'success' && strategyRes.data.data?.strategy_statistics) {
      updateStrategyChart(strategyRes.data.data.strategy_statistics)
    }
    
    if (overviewRes.data.data) {
      knowledgeStats.value = {
        questionCount: overviewRes.data.data.total_questions || 0,
        questionTypeCount: overviewRes.data.data.average_question_length || 0
      }
    }
  } catch (error) {
    console.error('获取数据失败，使用默认数据:', error)
  }
}

const updateStrategyChart = (strategyStats: any) => {
  const strategyColors = {
    'cot': '#10B981',
    'coloumn_sorting': '#3B82F6', 
    'schema_linking': '#F59E0B'
  }
  
  const strategyNames = {
    'cot': 'COT',
    'coloumn_sorting': '列排序',
    'schema_linking': '模式链接'
  }
  
  const pieData = Object.entries(strategyStats.counts).map(([key, value]) => ({
    value: value as number,
    name: strategyNames[key as keyof typeof strategyNames] || key,
    itemStyle: { color: strategyColors[key as keyof typeof strategyColors] || '#6B7280' }
  }))
  
  option3.value.series = [{
    name: '策略使用频率',
    type: 'pie',
    radius: ['25%', '60%'],
    center: ['50%', '40%'],
    data: pieData,
    emphasis: { 
      itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' }
    },
    label: {
      show: true,
      position: 'outside',
      formatter: '{b}\n{d}%',
      fontSize: 11,
      lineHeight: 14,
      color: '#333',
      fontWeight: 'normal',
      distanceToLabelLine: 5
    },
    labelLine: {
      show: true,
      length: 15,
      length2: 25,
      smooth: true,
      lineStyle: { color: '#999', width: 1 }
    },
    labelLayout: {
      hideOverlap: true,
      moveOverlap: 'shiftY'
    }
  }]
}

onMounted(async () => {
  document.addEventListener('click', handleClickOutside)
  await fetchData()
  await fetchPageData(currentPage.value, pageSize.value, searchKeyword.value)
  
  setTimeout(() => {
    if (mainChartRef.value && mainChartRef.value.chart) {
      console.log('添加图表点击事件监听')
      mainChartRef.value.chart.on('click', handleChartClick)
    }
  }, 1000)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  if (mainChartRef.value && mainChartRef.value.chart) {
    mainChartRef.value.chart.off('click', handleChartClick)
  }
})
</script>

<style scoped>
.kv-page-item {
  position: relative;
  overflow: hidden;
}

.kv-page-item-clickable:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.kv-page-item-clicking {
  background: linear-gradient(135deg, #667eea22, #764ba222) !important;
  border-color: #667eea !important;
  pointer-events: none;
}

.kv-page-item-content {
  transition: opacity 0.3s ease;
}

.kv-page-item-clicking .kv-page-item-content {
  opacity: 0.7;
}

.kv-page-item-loading {
  position: absolute;
  top: 50%;
  right: 12px;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #667eea;
  font-weight: 500;
}

.kv-page-item-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #e5e7eb;
  border-top: 2px solid #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.kv-page-item-clickable:active {
  transform: translateY(0);
  background: #e5e7eb;
}

.kv-detail-view {
  height: 100%;
  background: #ffffff;
  border-radius: 8px;
  overflow-y: auto;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.kv-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  padding-bottom: 15px;
  border-bottom: 1px solid #dee2e6;
}

.kv-detail-title {
  font-size: 24px;
  font-weight: bold;
  color: #343a40;
  margin: 0;
}

.kv-return-btn {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: bold;
  color: #495057;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.kv-return-btn:hover {
  background: #e9ecef;
  border-color: #adb5bd;
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

.kv-detail-section {
  margin-bottom: 40px;
}

.kv-section-title {
  font-size: 16px;
  font-weight: bold;
  color: #495057;
  margin-bottom: 15px;
}

.kv-detail-field {
  display: flex;
  margin-bottom: 20px;
  align-items: flex-start;
}

.kv-field-label {
  font-size: 16px;
  font-weight: bold;
  color: #495057;
  min-width: 80px;
  margin-right: 20px;
}

.kv-field-value {
  font-size: 14px;
  color: #212529;
  line-height: 1.5;
  flex: 1;
}

.kv-field-value.kv-answer {
  font-size: 16px;
  font-weight: bold;
  color: #28a745;
}

.kv-table-container {
  border: 1px solid #e9ecef;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.kv-data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.kv-data-table th {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  padding: 8px;
  text-align: left;
  font-size: 13px;
  font-weight: bold;
  color: #495057;
}

.kv-data-table td {
  border: 1px solid #e9ecef;
  padding: 6px 8px;
  color: #495057;
}

.kv-data-table tbody tr:nth-child(even) {
  background: #f8f9fa;
}

.kv-data-table tbody tr:nth-child(odd) {
  background: #ffffff;
}

.kv-table-more {
  padding: 10px;
  text-align: center;
  font-size: 12px;
  color: #868e96;
  font-style: italic;
  background: #f8f9fa;
  border-top: 1px solid #e9ecef;
}

.kv-strategy-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.kv-strategy-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  line-height: 1.5;
}

.kv-strategy-number {
  font-size: 14px;
  color: #495057;
  min-width: 20px;
}

.kv-strategy-label {
  font-size: 14px;
  color: #495057;
  font-weight: 500;
  min-width: 80px;
}

.kv-strategy-content {
  font-size: 14px;
  color: #212529;
  flex: 1;
}

.kv-wordcloud-chart {
  padding: 0 !important;
}

.kv-wordcloud-chart .kv-side-chart-section {
  margin: 0 !important;
  padding: 0 !important;
}

.kv-wordcloud-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  margin: 0;
  background: #fafafa;
  border-radius: 8px;
  overflow: hidden;
  width: 100%;
  height: 100%;
}

.kv-wordcloud-image {
  width: 130%;
  height: 100%;
  object-fit: contain;
  border-radius: 8px;
  transition: transform 0.3s ease;
}

.kv-wordcloud-image:hover {
  transform: scale(1.02);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
.kv-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #6b7280;
  font-size: 14px;
}

.kv-loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #f3f4f6;
  border-top: 3px solid #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 12px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.kv-no-data {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #9ca3af;
  font-size: 14px;
}

.kv-no-data svg {
  margin-bottom: 12px;
  opacity: 0.5;
}

.kv-page-item {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px 15px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.kv-page-item:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
  transform: translateY(-1px);
}

.kv-page-item-title {
  font-weight: 600;
  color: #374151;
  font-size: 14px;
}

.kv-page-item-desc {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.4;
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
}

.kv-page-item-id {
  font-size: 11px;
  color: #9ca3af;
  font-family: monospace;
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 4px;
  align-self: flex-start;
}

.kv-search-input:disabled,
.kv-page-size-select:disabled {
  background-color: #f9fafb;
  color: #9ca3af;
  cursor: not-allowed;
}

.kv-pagination span {
  font-size: 12px;
  color: #4b5563;
  text-align: center;
  line-height: 1.3;
}

.kv-pagination span small {
  font-size: 10px;
  color: #9ca3af;
}
.kv-knowledge-stats {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.3s ease;
}

.kv-knowledge-stats:hover {
  box-shadow: 0 4px 15px rgba(0,0,0,0.15);
}

.kv-knowledge-stats .kv-side-chart-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.kv-chart-wrapper {
  flex: 1;
  padding: 20px 10px;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.kv-independent-stats {
  display: flex;
  flex-direction: column;
  gap: 15px;
  width: 100%;
  max-width: 350px;
}

.kv-stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background: #f8f9fa;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.kv-stat-card:hover {
  background: #e9ecef;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.kv-stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.kv-stat-icon.learning {
  background: rgba(66, 133, 244, 0.1);
  color: #4285f4;
}

.kv-stat-icon.type {
  background: rgba(251, 188, 4, 0.1);
  color: #fbbc04;
}

.kv-stat-info {
  flex: 1;
}

.kv-stat-info .kv-stat-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 3px;
}

.kv-stat-info .kv-stat-value {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 2px;
}

.kv-stat-info .kv-stat-value.primary {
  color: #4285f4;
}

.kv-stat-info .kv-stat-value.warning {
  color: #fbbc04;
}

.kv-stat-info .kv-stat-unit {
  font-size: 11px;
  color: #999;
}
.kv-root {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: #f5f6fa;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.kv-header {
  flex-shrink: 0;
  width: 100%;
  height: 8vh;
  min-height: 50px;
  max-height: 80px;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 clamp(20px, 4vw, 60px);
  letter-spacing: 2px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  position: relative;
  z-index: 200;
}

.kv-title {
  font-size: clamp(20px, 3vw, 32px);
  font-weight: bold;
}

.kv-dropdown {
  position: relative;
}

.kv-dropdown-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  padding: 0.5rem 1rem;
  font-size: clamp(14px, 2vw, 16px);
  color: #fff;
  cursor: pointer;
  transition: all 0.3s ease;
  font-weight: 500;
  backdrop-filter: blur(10px);
}

.kv-dropdown-btn:hover {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.3);
  transform: translateY(-1px);
}

.kv-dropdown-btn svg:last-child {
  transition: transform 0.3s ease;
}

.kv-dropdown-btn svg:last-child.rotate {
  transform: rotate(180deg);
}

.kv-dropdown-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
  min-width: 200px;
  overflow: hidden;
  z-index: 1000;
  animation: fadeInDown 0.2s ease-out;
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.kv-dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 12px 16px;
  color: #374151;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  border-bottom: 1px solid #f3f4f6;
  user-select: none;
}

.kv-dropdown-item:last-child {
  border-bottom: none;
}

.kv-dropdown-item:hover {
  background: #f8fafc;
  color: #667eea;
}

.kv-dropdown-item:active {
  background: #e2e8f0;
}

.kv-dropdown-item svg {
  color: #6b7280;
  transition: color 0.2s ease;
  flex-shrink: 0;
}


.kv-dropdown-item:hover svg {
  color: #667eea;
}

.kv-dropdown-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: transparent;
}

.kv-content {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: clamp(12px, 1.5vw, 24px);
  padding: clamp(12px, 2vh, 24px);
  height: 92vh;
  overflow: hidden;
}

.kv-sidebar {
  flex-shrink: 0;
  width: clamp(260px, 28vw, 360px);
  background: #fff;
  border-radius: clamp(8px, 1vw, 16px);
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  display: flex;
  flex-direction: column;
  padding: clamp(12px, 2vh, 20px);
  overflow: hidden;
}

.kv-sidebar:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 25px rgba(0,0,0,0.12);
}

.kv-search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.kv-search-input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  font-size: 14px;
}
.kv-page-size-select {
  padding: 6px 8px;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  font-size: 14px;
  background: #fff;
}

.kv-page-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 5px; /* Add some padding for scrollbar */
}

.kv-page-item {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 10px 15px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.kv-page-item:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.kv-page-item-title {
  font-weight: 600;
  color: #374151;
  font-size: 15px;
}

.kv-page-item-desc {
  font-size: 13px;
  color: #6b7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kv-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 15px;
  padding-top: 10px;
  border-top: 1px solid #e5e7eb;
}

.kv-pagination button {
  padding: 8px 12px;
  background: #4F46E5;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: background 0.3s ease;
  white-space: nowrap;
}

.kv-pagination button:hover:not(:disabled) {
  background: #667eea;
}

.kv-pagination button:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  cursor: not-allowed;
}

.kv-pagination span {
  font-size: 14px;
  color: #4b5563;
}

.kv-main-chart {
  flex: 1.3;
  min-width: 0;
  background: #fff;
  border-radius: clamp(8px, 1vw, 16px);
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  display: flex;
  flex-direction: column;
  padding: clamp(12px, 2vh, 20px);
  overflow: hidden;
}

.kv-main-chart-title {
  flex-shrink: 0;
  font-size: clamp(16px, 2.5vw, 24px);
  font-weight: 700;
  color: #333;
  margin-bottom: clamp(8px, 1vh, 16px);
  text-align: center;
  background: linear-gradient(135deg, #667eea, #764ba2);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.kv-main-chart-section {
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow: hidden;
}

.kv-side-charts {
  flex: 0.7;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: clamp(12px, 1.5vh, 20px);
  overflow: hidden;
}

.kv-side-chart {
  flex: 1;
  min-height: 0;
  background: #fff;
  border-radius: clamp(8px, 1vw, 16px);
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  display: flex;
  flex-direction: column;
  padding: clamp(8px, 1.5vh, 16px);
  overflow: hidden;
  transition: all 0.3s ease;
}

.kv-side-chart:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 25px rgba(0,0,0,0.12);
}

.kv-side-chart-title {
  flex-shrink: 0;
  font-size: clamp(12px, 1.8vw, 18px);
  font-weight: 600;
  color: #764ba2;
  margin-bottom: clamp(4px, 0.8vh, 12px);
  text-align: center;
}

.kv-side-chart-section {
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow: hidden;
}

@media (max-width: 1200px) {
  .kv-content {
    gap: clamp(8px, 1vw, 16px);
    padding: clamp(8px, 1.5vh, 16px);
  }
  
  .kv-sidebar {
    width: clamp(220px, 25vw, 280px);
  }
  
  .kv-main-chart {
    flex: 1;
  }
}

@media (max-width: 900px) {
  .kv-sidebar {
    width: clamp(180px, 22vw, 240px);
  }
  
  .kv-main-chart {
    flex: 1;
  }
}

@media (max-width: 768px) {
  .kv-header {
    padding: 0 clamp(12px, 3vw, 24px);
  }
  
  .kv-dropdown-btn {
    padding: 0.4rem 0.75rem;
    font-size: 12px;
  }
  
  .kv-content {
    flex-direction: column;
    gap: clamp(6px, 1vh, 12px);
    padding: clamp(6px, 1vh, 12px);
  }
  
  .kv-sidebar {
    width: 100%;
    height: clamp(50px, 8vh, 70px);
  }
  
  .kv-side-charts {
    flex-direction: row;
    height: 35%;
  }
  
  .kv-main-chart {
    height: 55%;
    flex: none;
  }
}

@media (max-height: 600px) {
  .kv-header {
    height: 6vh;
    min-height: 40px;
  }
  
  .kv-content {
    height: 94vh;
  }
}

.kv-main-chart-section,
.kv-side-chart-section {
  position: relative;
}

.kv-main-chart-section > div,
.kv-side-chart-section > div {
  width: 100% !important;
  height: 100% !important;
  overflow: hidden !important;
}

::-webkit-scrollbar {
  display: none;
}

* {
  scrollbar-width: none;
  -ms-overflow-style: none;
}
</style>