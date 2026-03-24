<template>
  <div class="tv-root">
    <div class="tv-content">
      <!-- Top Section: Main Trends -->
      <div class="tv-chart-group top-row">
        <div class="tv-chart-container main-trend">
          <div class="tv-chart-header">
            <div class="tv-chart-title">教师指导能力展示</div>
            <div class="tv-chart-menu">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="1"></circle>
                <circle cx="19" cy="12" r="1"></circle>
                <circle cx="5" cy="12" r="1"></circle>
              </svg>
            </div>
          </div>
          <div class="tv-chart-wrapper">
            <v-chart class="tv-chart" :option="option1" autoresize />
          </div>
        </div>
        
        <div class="tv-chart-container main-trend">
          <div class="tv-chart-header">
            <div class="tv-chart-title">学徒独立解题能力展示</div>
            <div class="tv-chart-menu">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="1"></circle>
                <circle cx="19" cy="12" r="1"></circle>
                <circle cx="5" cy="12" r="1"></circle>
              </svg>
            </div>
          </div>
          <div class="tv-chart-wrapper">
            <v-chart class="tv-chart" :option="option2" autoresize />
          </div>
        </div>
      </div>
      
      <!-- Bottom Section: Detailed Analysis -->
      <div class="tv-chart-group bottom-row">
        <div class="tv-chart-container strategy-success">
          <div class="tv-chart-header">
            <div class="tv-chart-title">策略教学成功率</div>
          </div>
          <div class="tv-chart-wrapper">
            <v-chart class="tv-chart" :option="option3" autoresize />
          </div>
        </div>
        
        <div class="tv-chart-container stats-summary">
          <div class="tv-chart-header">
            <div class="tv-chart-title">学习记录统计</div>
          </div>
          <div class="tv-chart-wrapper no-padding">
            <div class="tv-independent-stats">
              <div class="tv-stat-card">
                <div class="tv-stat-icon learning">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
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
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>
                    <rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>
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
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
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
        
        <div class="tv-chart-container strategy-analysis">
          <div class="tv-chart-header">
            <div class="tv-chart-title">策略适用性分析</div>
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
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import api from '../../api'
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



const fetchDailyData = async (days: number = 30, endDate: string = new Date().toISOString().split('T')[0]) => {
  try {
    loading.value = true
    const response = await api.get('/statistics/daily-records', {
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
    const response = await api.get('/knowledge/strategy-statistics')
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
    const response = await api.get('/statistics/error-records-count')
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
    const response = await api.get('/statistics/learning-records-count')
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
    const response = await api.get('/statistics/strategy-categories')
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
    grid: { top: '15px', left: '3%', right: '4%', bottom: '3%', containLabel: true },
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
    grid: { top: '15px', left: '3%', right: '4%', bottom: '3%', containLabel: true },
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
    grid: { top: '20px', left: '3%', right: '4%', bottom: '3%', containLabel: true },
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
      right: '4%',
      top: '10px',
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
  
  fetchDailyData()
  fetchStrategyData()
  fetchErrorData()
  fetchTeachingData()
  fetchStrategyCategoriesData()
})

onUnmounted(() => {
})
</script>

<style scoped>
.tv-root {
  height: 100%;
  width: 100%;
  background-color: var(--bg-base);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: clamp(12px, 2vh, 24px);
  box-sizing: border-box;
}

.tv-content {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr;
  gap: clamp(16px, 3.5vh, 24px);
  max-width: 1600px;
  margin: 0 auto;
  width: 100%;
  min-height: min-content;
  padding-bottom: 24px;
}

.tv-chart-group {
  display: grid;
  gap: clamp(16px, 3vh, 24px);
  width: 100%;
}

.tv-chart-group.top-row {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 500px), 1fr));
}

.tv-chart-group.bottom-row {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 350px), 1fr));
}

.tv-chart-container {
  background: white;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  min-height: 300px;
}

@media (min-width: 1600px) {
  .tv-chart-container {
    min-height: 350px;
  }
}

.tv-chart-container:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
  border-color: var(--primary-color);
}

.tv-chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: clamp(12px, 2vh, 18px) 20px;
  border-bottom: 1px solid var(--border-light);
  background: #fafafa;
}

.tv-chart-title {
  font-size: clamp(14px, 1.2vw, 16px);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.tv-chart-wrapper {
  flex: 1;
  padding: clamp(12px, 2.5vh, 20px);
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.tv-chart-wrapper.no-padding {
  padding: 0;
}

.tv-chart {
  width: 100%;
  height: 100%;
}

.tv-independent-stats {
  display: grid;
  grid-template-rows: repeat(3, 1fr);
  height: 100%;
}

.tv-stat-card {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 10px 24px;
  border-bottom: 1px solid var(--border-light);
  transition: background 0.2s;
}

.tv-stat-card:last-child {
  border-bottom: none;
}

.tv-stat-card:hover {
  background: var(--bg-surface-hover);
}

.tv-stat-icon {
  width: clamp(40px, 4vw, 48px);
  height: clamp(40px, 4vw, 48px);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tv-stat-icon svg {
  width: clamp(20px, 2vw, 24px);
  height: clamp(20px, 2vw, 24px);
}

.tv-stat-icon.learning {
  background: var(--primary-light);
  color: var(--primary-color);
}

.tv-stat-icon.teaching {
  background: rgba(16, 185, 129, 0.1);
  color: var(--success-color);
}

.tv-stat-icon.error {
  background: rgba(245, 158, 11, 0.1);
  color: var(--warning-color);
}

.tv-stat-info {
  flex: 1;
}

.tv-stat-label {
  font-size: clamp(11px, 1vw, 13px);
  color: var(--text-secondary);
  font-weight: 500;
  margin-bottom: 2px;
}

.tv-stat-value {
  font-size: clamp(20px, 2.5vw, 28px);
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.02em;
}

.tv-stat-value.primary { color: var(--primary-color); }
.tv-stat-value.success { color: var(--success-color); }
.tv-stat-value.warning { color: var(--warning-color); }

.tv-stat-unit {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-tertiary);
  margin-top: 4px;
}

@media (max-width: 900px) {
  .tv-root {
    padding: 12px;
  }
}
</style>
