<template>
  <div class="tv-root">
    <div class="tv-header">
      <span class="tv-title">教学可视化大屏</span>
      
      <div class="tv-dropdown" ref="dropdownRef">
        <button class="tv-dropdown-btn" @click="toggleDropdown">
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
        
        <div v-show="showDropdown" class="tv-dropdown-menu">
          <div class="tv-dropdown-item" @click="handleQuizClick">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2h-4"></path>
              <polyline points="6,9 12,15 18,9"></polyline>
            </svg>
            答题界面
          </div>
          
          <div class="tv-dropdown-item" @click="handleKnowledgeClick">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14,2 14,8 20,8"></polyline>
            </svg>
            知识可视化
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="showDropdown" class="tv-dropdown-overlay" @click="closeDropdown"></div>
    
    <div class="tv-content">
      <div class="tv-top-charts">
        <div class="tv-chart-container tv-chart-large">
          <div class="tv-chart-header">
            <div class="tv-chart-title">教师指导能力展示</div>
            <div class="tv-chart-menu">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="5" r="1"></circle>
                <circle cx="12" cy="12" r="1"></circle>
                <circle cx="12" cy="19" r="1"></circle>
              </svg>
            </div>
          </div>
          <div class="tv-chart-wrapper">
            <v-chart class="tv-chart" :option="option1" autoresize />
          </div>
        </div>
        
        <div class="tv-chart-container tv-chart-large">
          <div class="tv-chart-header">
            <div class="tv-chart-title">学徒独⽴解题能⼒展示</div>
            <div class="tv-chart-menu">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="5" r="1"></circle>
                <circle cx="12" cy="12" r="1"></circle>
                <circle cx="12" cy="19" r="1"></circle>
              </svg>
            </div>
          </div>
          <div class="tv-chart-wrapper">
            <v-chart class="tv-chart" :option="option2" autoresize />
          </div>
        </div>
      </div>
      
      <div class="tv-bottom-charts">
        <div class="tv-chart-container tv-chart-small-extended">
          <div class="tv-chart-header">
            <div class="tv-chart-title">策略教学成功率</div>
            <div class="tv-chart-menu">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="5" r="1"></circle>
                <circle cx="12" cy="12" r="1"></circle>
                <circle cx="12" cy="19" r="1"></circle>
              </svg>
            </div>
          </div>
          <div class="tv-chart-wrapper">
            <v-chart class="tv-chart" :option="option3" autoresize />
          </div>
        </div>
        
        <div class="tv-chart-container tv-chart-small">
          <div class="tv-chart-header">
            <div class="tv-chart-title">学习记录统计</div>
            <div class="tv-chart-menu">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="5" r="1"></circle>
                <circle cx="12" cy="12" r="1"></circle>
                <circle cx="12" cy="19" r="1"></circle>
              </svg>
            </div>
          </div>
          <div class="tv-chart-wrapper">
            <div class="tv-independent-stats">
              <div class="tv-stat-card">
                <div class="tv-stat-icon learning">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 10v6M2 10l10-5 10 5-10 5z"></path>
                    <path d="m6 12 5 5 5-5"></path>
                  </svg>
                </div>
                <div class="tv-stat-info">
                  <div class="tv-stat-label">学习记录总数</div>
                  <div class="tv-stat-value primary">{{ dailyData?.data.total_statistics.total || 0 }}</div>
                  <div class="tv-stat-unit">条记录</div>
                </div>
              </div>
              
              <div class="tv-stat-card">
                <div class="tv-stat-icon teaching">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>
                    <rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>
                    <path d="M9 14l2 2 4-4"></path>
                  </svg>
                </div>
                <div class="tv-stat-info">
                  <div class="tv-stat-label">教导记录总数</div>
                  <div class="tv-stat-value success">{{ teachingData?.data.total_teaching_records || 0 }}</div>
                  <div class="tv-stat-unit">条记录</div>
                </div>
              </div>
              
              <div class="tv-stat-card">
                <div class="tv-stat-icon error">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="15" y1="9" x2="9" y2="15"></line>
                    <line x1="9" y1="9" x2="15" y2="15"></line>
                  </svg>
                </div>
                <div class="tv-stat-info">
                  <div class="tv-stat-label">错误记录总数</div>
                  <div class="tv-stat-value warning">{{ errorData?.data.total_error_records || 0 }}</div>
                  <div class="tv-stat-unit">条记录</div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="tv-chart-container tv-chart-large-extended">
          <div class="tv-chart-header">
            <div class="tv-chart-title">策略适用性分析</div>
            <div class="tv-chart-menu">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="5" r="1"></circle>
                <circle cx="12" cy="12" r="1"></circle>
                <circle cx="12" cy="19" r="1"></circle>
              </svg>
            </div>
          </div>
          <div class="tv-chart-wrapper">
            <v-chart class="tv-chart" :option="option5" autoresize />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import axios from 'axios'
import { use } from 'echarts/core'
import { 
  GraphicComponent, 
  TitleComponent, 
  TooltipComponent, 
  LegendComponent,
  GridComponent
} from 'echarts/components'
import { 
  BarChart,
  LineChart,
  PieChart,
  RadarChart
} from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'

use([
  GraphicComponent, 
  TitleComponent, 
  TooltipComponent, 
  LegendComponent,
  GridComponent,
  BarChart,
  LineChart,
  PieChart,
  RadarChart,
  CanvasRenderer
])

const router = useRouter()

type StrategyType = 'cot' | 'coloumn_sorting' | 'schema_linking'

interface StrategySuccessData {
  cot: number
  coloumn_sorting: number
  schema_linking: number
}

interface StrategyApiData {
  strategy_statistics_flag_1: {
    counts: StrategySuccessData
  }
  flag_2_count: number
}

interface StrategyApiResponse {
  status: string
  data: StrategyApiData
}

interface DailyStatistic {
  date: string
  flag_0: number
  flag_1: number
  flag_2: number
  total: number
}

interface TotalStatistic {
  flag_0: number
  flag_1: number
  flag_2: number
  total: number
}

interface DateRange {
  start_date: string
  end_date: string
  days: number
}

interface DailyApiData {
  daily_statistics: DailyStatistic[]
  total_statistics: TotalStatistic
  date_range: DateRange
}

interface DailyApiResponse {
  status: string
  data: DailyApiData
}

interface ErrorRecordsData {
  total_error_records: number
}

interface ErrorRecordsResponse {
  status: string
  data: ErrorRecordsData
}

interface TeachingRecordsData {
  total_teaching_records: number
}

interface TeachingRecordsResponse {
  status: string
  data: TeachingRecordsData
}

interface CategoryStatistic {
  category: string
  schema_linking: number
  coloumn_sorting: number
  cot: number
  total: number
}

interface StrategyCategoriesData {
  category_statistics: CategoryStatistic[]
  total_statistics: {
    schema_linking: number
    coloumn_sorting: number
    cot: number
    total: number
  }
}

interface StrategyCategoriesResponse {
  status: string
  data: StrategyCategoriesData
}

const strategyData = ref<StrategyApiResponse | null>(null)
const dailyData = ref<DailyApiResponse | null>(null)
const errorData = ref<ErrorRecordsResponse | null>(null)
const teachingData = ref<TeachingRecordsResponse | null>(null)
const strategyCategoriesData = ref<StrategyCategoriesResponse | null>(null)
const loading = ref(false)

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
  router.push('/')
}

const handleKnowledgeClick = () => {
  closeDropdown()
  router.push('/knowledge-visualization')
}

const fetchDailyData = async (days: number = 30, endDate: string = new Date().toISOString().split('T')[0]) => {
  try {
    loading.value = true
    const response = await axios.get('http://127.0.0.1:8000/api/statistics/daily-records', {
      params: { days, end_date: endDate }
    })
    dailyData.value = response.data
    generateOption1()
    generateOption2()
  } catch (error) {
    console.error('获取每日数据失败:', error)
  } finally {
    loading.value = false
  }
}

const fetchStrategyData = async () => {
  try {
    loading.value = true
    const response = await axios.get('http://127.0.0.1:8000/api/knowledge/strategy-statistics')
    strategyData.value = response.data
    generateOption3()
  } catch (error) {
    console.error('获取策略数据失败:', error)
  } finally {
    loading.value = false
  }
}

const fetchErrorData = async () => {
  try {
    loading.value = true
    const response = await axios.get('http://127.0.0.1:8000/api/statistics/error-records-count')
    errorData.value = response.data
  } catch (error) {
    console.error('获取错误记录数据失败:', error)
  } finally {
    loading.value = false
  }
}

const fetchTeachingData = async () => {
  try {
    loading.value = true
    const response = await axios.get('http://127.0.0.1:8000/api/statistics/learning-records-count')
    teachingData.value = response.data
  } catch (error) {
    console.error('获取教导记录数据失败:', error)
  } finally {
    loading.value = false
  }
}

const fetchStrategyCategoriesData = async () => {
  try {
    loading.value = true
    const response = await axios.get('http://127.0.0.1:8000/api/statistics/strategy-categories')
    strategyCategoriesData.value = response.data
    generateOption5()
  } catch (error) {
    console.error('获取策略分类数据失败:', error)
  } finally {
    loading.value = false
  }
}

const calculateDailySuccessRate = (daily: DailyStatistic): number => {
  const successCount = daily.flag_1
  const failureCount = daily.flag_2
  const totalCount = successCount + failureCount
  
  return totalCount === 0 ? 0 : Number(((successCount / totalCount) * 100).toFixed(2))
}

const calculateStudentCorrectRate = (daily: DailyStatistic): number => {
  const correctCount = daily.flag_0
  const totalCount = daily.total
  
  return totalCount === 0 ? 0 : Number(((correctCount / totalCount) * 100).toFixed(2))
}

const calculateSuccessRate = (strategy: StrategyType): number => {
  if (!strategyData.value) return 0
  
  const successCount = strategyData.value.data.strategy_statistics_flag_1.counts[strategy]
  const failureCount = strategyData.value.data.flag_2_count
  const totalCount = successCount + failureCount
  
  return totalCount === 0 ? 0 : Number(((successCount / totalCount) * 100).toFixed(2))
}

const generateOption1 = () => {
  if (!dailyData.value) return

  const filteredStats = dailyData.value.data.daily_statistics.filter(item => item.total > 0)
  const dates = filteredStats.map(item => item.date.slice(5))
  const successRates = filteredStats.map(item => calculateDailySuccessRate(item))

  option1.value = {
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLabel: { color: '#666', fontSize: 12 },
      axisLine: { lineStyle: { color: chartColors.borderGray } }
    },
    yAxis: {
      type: 'value',
      name: '教学成功率(%)',
      nameTextStyle: { color: '#666', fontSize: 12 },
      axisLabel: { color: '#666', formatter: '{value}%' },
      axisLine: { lineStyle: { color: chartColors.borderGray } },
      splitLine: { lineStyle: { color: chartColors.lightGray } }
    },
    series: [{
      name: '每日教学成功率',
      type: 'line',
      smooth: true,
      data: successRates,
      lineStyle: { width: 3, color: chartColors.primary },
      itemStyle: { color: chartColors.primary },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(66, 133, 244, 0.3)' },
            { offset: 1, color: 'rgba(66, 133, 244, 0.05)' }
          ]
        }
      }
    }],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(50, 50, 50, 0.8)',
      borderColor: 'rgba(50, 50, 50, 0.8)',
      textStyle: { color: '#fff' },
      formatter: (params: any) => {
        const param = params[0]
        const daily = filteredStats[param.dataIndex]
        
        return `
          <div style="padding: 5px;">
            <strong>${daily.date}</strong><br/>
            教学成功率: ${param.value}%<br/>
            成功案例: ${daily.flag_1}<br/>
            失败案例: ${daily.flag_2}<br/>
            总案例: ${daily.flag_1 + daily.flag_2}
          </div>
        `
      }
    }
  }
}

const generateOption2 = () => {
  if (!dailyData.value) return

  const filteredStats = dailyData.value.data.daily_statistics.filter(item => item.total > 0)
  const dates = filteredStats.map(item => item.date.slice(5))
  const correctRates = filteredStats.map(item => calculateStudentCorrectRate(item))

  option2.value = {
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLabel: { color: '#666', fontSize: 12 },
      axisLine: { lineStyle: { color: chartColors.borderGray } }
    },
    yAxis: {
      type: 'value',
      name: '学生做对率(%)',
      nameTextStyle: { color: '#666', fontSize: 12 },
      axisLabel: { color: '#666', formatter: '{value}%' },
      axisLine: { lineStyle: { color: chartColors.borderGray } },
      splitLine: { lineStyle: { color: chartColors.lightGray } }
    },
    series: [{
      name: '学生自己做对率',
      type: 'line',
      smooth: true,
      data: correctRates,
      lineStyle: { width: 3, color: chartColors.success },
      itemStyle: { color: chartColors.success },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(52, 168, 83, 0.3)' },
            { offset: 1, color: 'rgba(52, 168, 83, 0.05)' }
          ]
        }
      }
    }],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(50, 50, 50, 0.8)',
      borderColor: 'rgba(50, 50, 50, 0.8)',
      textStyle: { color: '#fff' },
      formatter: (params: any) => {
        const param = params[0]
        const daily = filteredStats[param.dataIndex]
        
        return `
          <div style="padding: 5px;">
            <strong>${daily.date}</strong><br/>
            学生做对率: ${param.value}%<br/>
            自己做对: ${daily.flag_0}<br/>
            总题数: ${daily.total}
          </div>
        `
      }
    }
  }
}

const generateOption3 = () => {
  if (!strategyData.value) return

  const rates = {
    cot: calculateSuccessRate('cot'),
    sorting: calculateSuccessRate('coloumn_sorting'),
    linking: calculateSuccessRate('schema_linking')
  }

  option3.value = {
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: ['COT', '列排序', '模式链接'],
      axisLabel: { color: '#666', fontSize: 12 },
      axisLine: { lineStyle: { color: chartColors.borderGray } }
    },
    yAxis: {
      type: 'value',
      name: '教学成功率(%)',
      nameTextStyle: { color: '#666', fontSize: 12 },
      axisLabel: { color: '#666', formatter: '{value}%' },
      axisLine: { lineStyle: { color: chartColors.borderGray } },
      splitLine: { lineStyle: { color: chartColors.lightGray } }
    },
    series: [{
      name: '教学成功率',
      type: 'bar',
      data: [
        { value: rates.cot, itemStyle: { color: chartColors.primary } },
        { value: rates.sorting, itemStyle: { color: chartColors.success } },
        { value: rates.linking, itemStyle: { color: chartColors.warning } }
      ],
      barWidth: '60%',
      label: { show: true, position: 'top', color: '#333', fontSize: 12, formatter: '{c}%' }
    }],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(50, 50, 50, 0.8)',
      borderColor: 'rgba(50, 50, 50, 0.8)',
      textStyle: { color: '#fff' },
      formatter: (params: any) => {
        const param = params[0]
        const strategies: StrategyType[] = ['cot', 'coloumn_sorting', 'schema_linking']
        const strategy = strategies[param.dataIndex]
        const successCount = strategyData.value!.data.strategy_statistics_flag_1.counts[strategy]
        const failureCount = strategyData.value!.data.flag_2_count
        
        return `
          <div style="padding: 5px;">
            <strong>${param.name}</strong><br/>
            教学成功率: ${param.value}%<br/>
            成功案例: ${successCount}<br/>
            失败案例: ${failureCount}<br/>
            总案例: ${successCount + failureCount}
          </div>
        `
      }
    }
  }
}

const generateOption5 = () => {
  if (!strategyCategoriesData.value) return

  const categories = strategyCategoriesData.value.data.category_statistics
  const categoryNames = categories.map(item => item.category)
  const cotData = categories.map(item => item.cot)
  const sortingData = categories.map(item => item.coloumn_sorting)  
  const linkingData = categories.map(item => item.schema_linking)

  option5.value = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      backgroundColor: 'rgba(50, 50, 50, 0.8)',
      borderColor: 'rgba(50, 50, 50, 0.8)',
      textStyle: { color: '#fff' },
      formatter: (params: any) => {
        const categoryIndex = params[0].dataIndex
        const category = categories[categoryIndex]
        
        const strategies = [
          { name: 'COT', count: category.cot },
          { name: '列排序', count: category.coloumn_sorting },
          { name: '模式链接', count: category.schema_linking }
        ]
        const bestStrategy = strategies.reduce((max, current) => 
          current.count > max.count ? current : max
        )
        
        return `
          <div style="padding: 8px;">
            <strong>${category.category} 类问题</strong><br/>
            COT: ${category.cot} 次<br/>
            列排序: ${category.coloumn_sorting} 次<br/>
            模式链接: ${category.schema_linking} 次<br/>
            <div style="margin-top: 6px; padding-top: 6px; border-top: 1px solid #666;">
              <strong>最适用策略: ${bestStrategy.name} (${bestStrategy.count}次)</strong>
            </div>
            总计: ${category.total} 次
          </div>
        `
      }
    },
    legend: {
      data: ['COT', '列排序', '模式链接'],
      bottom: '0%',
      textStyle: { fontSize: 10, color: '#666' }
    },
    grid: {
      left: '0%',
      right: '0%',
      top: '0%',
      bottom: '8%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      axisLabel: { color: '#666' },
      axisLine: { lineStyle: { color: chartColors.borderGray } },
      splitLine: { lineStyle: { color: chartColors.lightGray } }
    },
    yAxis: {
      type: 'category',
      data: categoryNames,
      axisLabel: { 
        color: '#666', 
        fontSize: 11
      },
      axisLine: { lineStyle: { color: chartColors.borderGray } }
    },
    series: [
      {
        name: 'COT',
        type: 'bar',
        stack: 'total',
        label: {
          show: true
        },
        emphasis: {
          focus: 'series'
        },
        data: cotData,
        itemStyle: { color: chartColors.primary }
      },
      {
        name: '列排序',
        type: 'bar', 
        stack: 'total',
        label: {
          show: true
        },
        emphasis: {
          focus: 'series'
        },
        data: sortingData,
        itemStyle: { color: chartColors.success }
      },
      {
        name: '模式链接',
        type: 'bar',
        stack: 'total',
        label: {
          show: true
        },
        emphasis: {
          focus: 'series'
        },
        data: linkingData,
        itemStyle: { color: chartColors.warning }
      }
    ]
  }
}

const chartColors = {
  primary: '#4285f4',
  success: '#34a853', 
  warning: '#fbbc04',
  gray: '#999',
  lightGray: '#f0f0f0',
  borderGray: '#e6e6e6'
} as const

const option1 = ref<EChartsOption>({})

const option2 = ref<EChartsOption>({})

const option3 = ref<EChartsOption>({})

const option5 = ref<EChartsOption>({})

onMounted(() => {
  document.addEventListener('click', (event) => {
    if (dropdownRef.value && !dropdownRef.value.contains(event.target)) {
      showDropdown.value = false
    }
  })
  
  fetchDailyData()
  fetchStrategyData()
  fetchErrorData()
  fetchTeachingData()
  fetchStrategyCategoriesData()
})

onUnmounted(() => {
  document.removeEventListener('click', () => {})
})
</script>

<style scoped>
.tv-root {
  height: 100vh;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tv-header {
  height: 60px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  position: relative;
  z-index: 1000;
}

.tv-title {
  font-size: 20px;
  font-weight: 700;
  text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
}

.tv-dropdown {
  position: relative;
}

.tv-dropdown-btn {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: #fff;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
}

.tv-dropdown-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

.tv-dropdown-btn svg.rotate {
  transform: rotate(180deg);
}

.tv-dropdown-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 8px 25px rgba(0,0,0,0.15);
  min-width: 160px;
  overflow: hidden;
  border: 1px solid #e6e6e6;
}

.tv-dropdown-item {
  padding: 12px 16px;
  color: #333;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  transition: all 0.2s ease;
}

.tv-dropdown-item:hover {
  background: #f8f9fa;
  color: #667eea;
}

.tv-dropdown-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 999;
}

.tv-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  gap: 20px;
  overflow: hidden;
}

.tv-top-charts {
  flex: 1;
  display: flex;
  gap: 20px;
  min-height: 0;
}

.tv-bottom-charts {
  flex: 1;
  display: flex;
  gap: 20px;
  min-height: 0;
}

.tv-chart-container {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.3s ease;
}

.tv-chart-container:hover {
  box-shadow: 0 4px 15px rgba(0,0,0,0.15);
}

.tv-chart-large {
  flex: 1;
}

.tv-chart-medium {
  flex: 1;
}

.tv-chart-small {
  flex: 0.6;
}

.tv-chart-small-extended {
  flex: 1.2;
}

.tv-chart-large-extended {
  flex: 1.2;
}

.tv-chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
}

.tv-chart-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.tv-chart-menu {
  cursor: pointer;
  color: #999;
  transition: color 0.2s ease;
}

.tv-chart-menu:hover {
  color: #667eea;
}

.tv-chart-wrapper {
  flex: 1;
  padding: 16px 20px 20px;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.tv-chart {
  width: 100%;
  height: 100%;
  min-height: 200px;
}

.tv-participation-stats {
  display: flex;
  align-items: center;
  gap: 30px;
  height: 100%;
}

.tv-progress-circle {
  position: relative;
  flex-shrink: 0;
}

.tv-progress-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.tv-progress-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #4285f4;
}

.tv-progress-label {
  display: block;
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

.tv-stats-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tv-stats-row {
  display: flex;
  align-items: center;
}

.tv-stats-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 12px 0;
  border-bottom: 1px solid #f5f5f5;
}

.tv-stats-label {
  font-size: 14px;
  color: #666;
  flex: 1;
}

.tv-stats-value {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-right: 16px;
}

.tv-stats-change {
  font-size: 14px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
}

.tv-stats-change.positive {
  color: #34a853;
  background: rgba(52, 168, 83, 0.1);
}

.tv-stats-change.negative {
  color: #ea4335;
  background: rgba(234, 67, 53, 0.1);
}

.tv-chart-table {
  flex: 1;
  overflow-y: auto;
}

.tv-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.tv-table th {
  background: #f8f9fa;
  color: #666;
  font-weight: 600;
  padding: 12px 8px;
  text-align: left;
  border-bottom: 2px solid #e9ecef;
  font-size: 13px;
}

.tv-table td {
  padding: 12px 8px;
  border-bottom: 1px solid #f0f0f0;
  color: #333;
}

.tv-table tr:hover {
  background: #f8f9fa;
}

.tv-statistics-container {
  display: flex;
  justify-content: space-around;
  padding: 20px 0;
  border-bottom: 1px solid #f0f0f0;
  margin-bottom: 20px;
}

.tv-stat-item {
  text-align: center;
}

.tv-stat-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.tv-stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #4285f4;
  margin-bottom: 4px;
}

.tv-stat-value.error {
  color: #fbbc04;
}

.tv-stat-unit {
  font-size: 14px;
  color: #999;
}

.tv-chart-area {
  flex: 1;
  min-height: 200px;
}

.tv-independent-stats {
  display: flex;
  flex-direction: column;
  gap: clamp(4px, 1vh, 8px);
  height: 100%;
  justify-content: center;
  padding: clamp(8px, 1.5vh, 12px) 0;
}

.tv-stat-card {
  display: flex;
  align-items: center;
  gap: clamp(15px, 3vw, 30px);
  padding: clamp(8px, 1.2vh, 12px) clamp(12px, 2vw, 18px);
  background: #f8f9fa;
  border-radius: 8px;
  transition: all 0.3s ease;
  margin: clamp(1px, 0.2vh, 3px) 0;
  min-height: clamp(60px, 8vh, 80px);
}

.tv-stat-card:hover {
  background: #e9ecef;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.tv-stat-icon {
  width: clamp(32px, 5vw, 48px);
  height: clamp(32px, 5vw, 48px);
  border-radius: clamp(8px, 1.5vw, 12px);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tv-stat-icon svg {
  width: clamp(16px, 3vw, 24px);
  height: clamp(16px, 3vw, 24px);
}

.tv-stat-icon.learning {
  background: rgba(66, 133, 244, 0.1);
  color: #4285f4;
}

.tv-stat-icon.teaching {
  background: rgba(52, 168, 83, 0.1);
  color: #34a853;
}

.tv-stat-icon.error {
  background: rgba(251, 188, 4, 0.1);
  color: #fbbc04;
}

.tv-stat-info {
  flex: 1;
}

.tv-stat-info .tv-stat-label {
  font-size: clamp(12px, 1.8vw, 14px);
  color: #666;
  margin-bottom: clamp(2px, 0.5vh, 4px);
  line-height: 1.2;
}

.tv-stat-info .tv-stat-value {
  font-size: clamp(18px, 3.5vw, 28px);
  font-weight: 700;
  margin-bottom: clamp(1px, 0.3vh, 2px);
  line-height: 1.1;
}

.tv-stat-info .tv-stat-value.primary {
  color: #4285f4;
}

.tv-stat-info .tv-stat-value.success {
  color: #34a853;
}

.tv-stat-info .tv-stat-value.warning {
  color: #fbbc04;
}

.tv-stat-info .tv-stat-unit {
  font-size: clamp(10px, 1.5vw, 12px);
  color: #999;
  line-height: 1.2;
}

.status-done {
  color: #34a853;
  background: rgba(52, 168, 83, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.status-progress {
  color: #fbbc04;
  background: rgba(251, 188, 4, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.status-cancelled {
  color: #ea4335;
  background: rgba(234, 67, 53, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

@media (max-width: 1200px) {
  .tv-content {
    gap: 16px;
    padding: 16px;
  }
  
  .tv-top-charts,
  .tv-bottom-charts {
    gap: 16px;
  }
}

@media (max-width: 768px) {
  .tv-content {
    flex-direction: column;
    gap: 12px;
    padding: 12px;
  }
  
  .tv-top-charts,
  .tv-bottom-charts {
    flex-direction: column;
    gap: 12px;
  }
  
  .tv-participation-stats {
    flex-direction: column;
    gap: 20px;
  }
  
  .tv-chart-container {
    min-height: 250px;
  }
}

.tv-chart,
.tv-chart > div,
.tv-chart > div > div {
  width: 100% !important;
  height: 100% !important;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.tv-chart-container {
  animation: fadeInUp 0.6s ease-out;
}

.tv-chart-container:nth-child(1) { animation-delay: 0.1s; }
.tv-chart-container:nth-child(2) { animation-delay: 0.2s; }
.tv-bottom-charts .tv-chart-container:nth-child(1) { animation-delay: 0.3s; }
.tv-bottom-charts .tv-chart-container:nth-child(2) { animation-delay: 0.4s; }
.tv-bottom-charts .tv-chart-container:nth-child(3) { animation-delay: 0.5s; }
</style>
