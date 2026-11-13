import axios from 'axios';

const API = axios.create({
    baseURL: 'http://localhost:8000/api',
});

export const startTask = async (task, repoUrl) => {
    const response = await API.post('/start', { task, repo_url: repoUrl });
    return response.data;
};

export const sendFeedback = async (threadId, feedback) => {
    const response = await API.post('/feedback', { thread_id: threadId, feedback });
    return response.data;
};