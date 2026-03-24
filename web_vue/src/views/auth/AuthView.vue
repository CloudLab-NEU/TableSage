<template>
    <div class="auth-container">
        <div class="auth-card">
            <div class="auth-header">
                <h1>TableSage</h1>
                <p>{{ isLogin ? '登录以继续' : '注册新账号' }}</p>
            </div>

            <form @submit.prevent="handleSubmit" class="auth-form">
                <div class="form-group">
                    <label>用户名</label>
                    <input v-model="form.username" type="text" placeholder="输入用户名" required />
                </div>

                <div class="form-group">
                    <label>密码</label>
                    <input v-model="form.password" type="password" placeholder="输入密码" required />
                </div>

                <div v-if="error" class="error-msg">{{ error }}</div>

                <button type="submit" class="auth-btn" :disabled="loading">
                    {{ loading ? '处理中...' : (isLogin ? '登录' : '注册') }}
                </button>
            </form>

            <div class="auth-footer">
                <a @click="isLogin = !isLogin">
                    {{ isLogin ? '没有账号？立即注册' : '已有账号？点击登录' }}
                </a>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import api from '../../api'

const router = useRouter()
const isLogin = ref(true)
const loading = ref(false)
const error = ref('')

const form = reactive({
    username: '',
    password: ''
})

const handleSubmit = async () => {
    loading.value = true
    error.value = ''

    try {
        const endpoint = isLogin.value ? '/auth/login' : '/auth/register'
        const res = await api.post(endpoint, form) as any

        if (res.user_id) {
            localStorage.setItem('tablesage-user', JSON.stringify(res))
            router.push('/')
        }
    } catch (err: any) {
        error.value = err.response?.data?.detail || '认证失败'
    } finally {
        loading.value = false
    }
}
</script>

<style scoped>
.auth-container {
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
}

.auth-card {
    background: white;
    padding: 40px;
    border-radius: 20px;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
    width: 100%;
    max-width: 400px;
}

.auth-header {
    text-align: center;
    margin-bottom: 30px;
}

.auth-header h1 {
    font-size: 28px;
    font-weight: 800;
    color: #1e293b;
    margin-bottom: 8px;
    letter-spacing: -0.5px;
}

.auth-header p {
    color: #64748b;
    font-size: 14px;
}

.form-group {
    margin-bottom: 20px;
}

.form-group label {
    display: block;
    font-size: 14px;
    font-weight: 600;
    color: #475569;
    margin-bottom: 8px;
}

.form-group input {
    width: 100%;
    padding: 12px 16px;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    font-size: 14px;
    transition: all 0.2s;
    box-sizing: border-box;
}

.form-group input:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.error-msg {
    color: #ef4444;
    font-size: 13px;
    margin-bottom: 15px;
    text-align: center;
}

.auth-btn {
    width: 100%;
    padding: 12px;
    background: #3b82f6;
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    font-size: 16px;
    cursor: pointer;
    transition: all 0.2s;
}

.auth-btn:hover {
    background: #2563eb;
    transform: translateY(-1px);
}

.auth-btn:disabled {
    background: #94a3b8;
    cursor: not-allowed;
    transform: none;
}

.auth-footer {
    margin-top: 20px;
    text-align: center;
}

.auth-footer a {
    font-size: 14px;
    color: #3b82f6;
    text-decoration: none;
    cursor: pointer;
}

.auth-footer a:hover {
    text-decoration: underline;
}
</style>
