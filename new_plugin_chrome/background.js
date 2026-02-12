// WebSocket 连接
let ws = null;
let reconnectInterval = null;
const WS_URL = 'ws://localhost:5000';
let isConnecting = false; // 防止重复连接

// 初始化 WebSocket 连接
function connectWebSocket() {
    // 如果已经在连接或已连接，直接返回
    if (isConnecting || (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN))) {
        console.log('WebSocket 已连接或正在连接中，跳过');
        return;
    }

    isConnecting = true;
    console.log('正在连接 WebSocket...');

    ws = new WebSocket(WS_URL);

    ws.onopen = function () {
        console.log('WebSocket 连接成功');
        isConnecting = false;
        // 清除重连定时器
        if (reconnectInterval) {
            clearInterval(reconnectInterval);
            reconnectInterval = null;
        }
    };

    ws.onmessage = function (event) {
        console.log('收到消息:', event.data);
        handleMessage(event.data);
    };

    ws.onerror = function (error) {
        console.error('WebSocket 错误:', error);
        isConnecting = false;
    };

    ws.onclose = function () {
        console.log('WebSocket 连接断开，3秒后重连...');
        isConnecting = false;
        ws = null;
        // 3秒后重连
        if (!reconnectInterval) {
            reconnectInterval = setInterval(connectWebSocket, 3000);
        }
    };
}

// 处理收到的消息
function handleMessage(message) {
    // 消息格式: command:content;
    // 解析消息
    const match = message.match(/^(\w+):([^;]*);$/);
    if (!match) {
        console.error('消息格式错误:', message);
        sendResponse('error:invalid_format;');
        return;
    }

    const command = match[1];
    const content = match[2];

    console.log('解析命令:', command, '内容:', content);

    switch (command) {
        case 'check_url':
            handleCheckUrl(content);
            break;
        case 'click_element':
            handleClickElement(content);
            break;
        case 'open_url':
            handleOpenUrl(content);
            break;
        case 'buy_fat':
            handleBuyFat(content);
            break;
        case 'get_fats':
            handleGetFats(content);
            break;
        default:
            console.error('未知命令:', command);
            sendResponse('error:unknown_command;');
    }
}

// 发送响应给后端
function sendResponse(message) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(message);
        console.log('发送响应:', message);
    } else {
        console.error('WebSocket 未连接，无法发送响应');
    }
}
function handleBuyFat(content) {
    console.log('处理 buy_fat 命令，内容:', content);

    // 解析参数: username,fat_amount,order_id (新格式，包含订单ID)
    const parts = content.split(',');
    if (parts.length !== 3) {
        console.error('参数格式错误，应为: username,fat_amount,order_id');
        sendResponse('buy_fat:error:invalid_params;');
        return;
    }

    const username = parts[0].trim();
    const fatAmount = parts[1].trim();
    const orderId = parts[2].trim();

    console.log('购买参数 - 用户名:', username, '数量:', fatAmount, '订单ID:', orderId);

    // 开始购买
    // 检查当前页面是否包含wallet
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
        const tab = tabs[0];
        if (!tab) {
            sendResponse('buy_fat:no_active_tab;');
            return;
        }
        chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: () => {
                return document.body.innerText.includes('wallet');
            }
        }, (results) => {
            if (results && results[0] && results[0].result) {
                console.log('页面包含 wallet，执行购买操作');
                // 模拟购买操作
                chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    func: (username, fatAmount) => {
                        // 这里放置购买的具体代码
                        console.log('执行购买 fat 的代码');
                        // 为name=username的input赋值
                        const usernameInput = document.querySelector('input[name="username"]');
                        if (usernameInput) {
                            usernameInput.value = username;
                        }
                        // 为Amount赋值 name=amount
                        const amountInput = document.querySelector('input[name="amount"]');
                        if (amountInput) {
                            amountInput.value = fatAmount;
                        }
                        // 点击发送按钮 id=sendButton
                        const radio = document.querySelector('input[name="fee_payer"][value="they"]');
                        if (radio) {
                            radio.checked = true;
                            radio.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                        const submitButton = document.querySelector('.formSubmitRow-main .formSubmitRow-controls button');
                        if (submitButton) {
                            submitButton.click();
                        }
                    },
                                    args: [username, fatAmount]
                                });
                                // 等待5秒后检查页面是否有错误提示
                                setTimeout(() => {
                                    chrome.scripting.executeScript({
                                        target: { tabId: tab.id },
                                        func: () => {
                                            // 查找包含警告信息的overlay容器
                                            const overlayContainer = document.querySelector('.overlay-container.is-active');
                                            if (overlayContainer) {
                                                // 在overlay容器内查找blockMessage
                                                const blockMessage = overlayContainer.querySelector('.blockMessage');
                                                if (blockMessage) {
                                                    // 获取错误信息并去除多余空白
                                                    const errorMsg = blockMessage.textContent.trim();
                                                    return errorMsg;
                                                }
                                            }
                                            return null;
                                        }
                                    }, (results) => {
                                        if (results && results[0] && results[0].result) {
                                            // 有错误信息
                                            const errorMsg = results[0].result;
                                            console.log('购买失败，错误信息:', errorMsg);
                                            sendResponse(`buy_fat:fail,${orderId},${errorMsg};`);
                                        } else {
                                            // 没有错误信息，购买成功
                                            console.log('购买成功');
                                            sendResponse(`buy_fat:success,${orderId};`);
                                        }
                                    });
                                }, 5000);
                                } else {                console.log('页面不包含 wallet，正在跳转');
                // 跳转到购买页面
                chrome.tabs.update(tab.id, { url: 'https://fatality.win/wallet/wallet/send' });
                // 循环等待至页面加载完成
                const checkPageLoaded = setInterval(() => {
                    chrome.scripting.executeScript({
                        target: { tabId: tab.id },
                        func: () => {
                            return document.readyState === 'complete';
                        }
                    }, (results) => {
                        if (results && results[0] && results[0].result) {
                            clearInterval(checkPageLoaded);
                            console.log('购买页面加载完成，执行购买操作');
                            // 模拟购买操作
                            chrome.scripting.executeScript({
                                target: { tabId: tab.id },
                                func: (username, fatAmount) => {
                                    // 为name=username的input赋值
                                    const usernameInput = document.querySelector('input[name="username"]');
                                    if (usernameInput) {
                                        usernameInput.value = username;
                                    }
                                    // 为Amount赋值 name=amount
                                    const amountInput = document.querySelector('input[name="amount"]');
                                    if (amountInput) {
                                        amountInput.value = fatAmount;
                                    }
                                    // 点击发送按钮
                                    const radio = document.querySelector('input[name="fee_payer"][value="they"]');
                                    if (radio) {
                                        radio.checked = true;
                                        radio.dispatchEvent(new Event('change', { bubbles: true }));
                                    }
                                    const submitButton = document.querySelector('.formSubmitRow-main .formSubmitRow-controls button');
                                    if (submitButton) {
                                        submitButton.click();
                                    }
                                },
                                args: [username, fatAmount]
                            });
                            // 等待5秒后检查页面是否有错误提示
                            setTimeout(() => {
                                chrome.scripting.executeScript({
                                    target: { tabId: tab.id },
                                    func: () => {
                                        // 查找包含警告信息的overlay容器
                                        const overlayContainer = document.querySelector('.overlay-container.is-active');
                                        if (overlayContainer) {
                                            // 在overlay容器内查找blockMessage
                                            const blockMessage = overlayContainer.querySelector('.blockMessage');
                                            if (blockMessage) {
                                                // 获取错误信息并去除多余空白
                                                const errorMsg = blockMessage.textContent.trim();
                                                return errorMsg;
                                            }
                                        }
                                        return null;
                                    }
                                }, (results) => {
                                    if (results && results[0] && results[0].result) {
                                        // 有错误信息
                                        const errorMsg = results[0].result;
                                        console.log('购买失败，错误信息:', errorMsg);
                                        sendResponse(`buy_fat:fail,${orderId},${errorMsg};`);
                                    } else {
                                        // 没有错误信息，购买成功
                                        console.log('购买成功');
                                        sendResponse(`buy_fat:success,${orderId};`);
                                    }
                                });
                            }, 5000);
                        }
                    });
                }, 1000);
            }
        });
    });
}

// 处理 get_fats 命令
async function handleGetFats(content) {
    console.log('处理 get_fats 命令');

    try {
        // 获取当前活跃标签页
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (!tab) {
            sendResponse('get_fats:error:no_active_tab;');
            return;
        }

        const walletUrl = 'https://fatality.win/wallet/wallet';

        // 检查当前是否在 wallet 页面
        if (tab.url === walletUrl) {
            console.log('已在 wallet 页面，刷新页面');
            await chrome.tabs.reload(tab.id);
        } else {
            console.log('跳转到 wallet 页面');
            await chrome.tabs.update(tab.id, { url: walletUrl });
        }

        // 等待页面加载完成
        await waitForPageLoad(tab.id);

        // 获取钱包余额
        const result = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: () => {
                const balanceElement = document.querySelector('.wallet-balance.positive');
                if (balanceElement) {
                    // 获取文本内容并提取纯整数
                    const text = balanceElement.textContent.trim();
                    const balance = parseInt(text, 10);
                    return isNaN(balance) ? 0 : balance;
                }
                return null;
            }
        });

        if (result && result[0] && result[0].result !== null) {
            const balance = result[0].result;
            console.log('获取到余额:', balance);
            sendResponse(`get_fats:${balance};`);
        } else {
            console.error('未找到余额元素');
            sendResponse('get_fats:error:balance_not_found;');
        }
    } catch (error) {
        console.error('处理 get_fats 异常:', error);
        sendResponse('get_fats:error;');
    }
}
// 处理 check_url 命令
async function handleCheckUrl(urlContent) {
    try {
        // 获取当前活跃标签页
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (!tab) {
            sendResponse('check_url:no_active_tab;');
            return;
        }

        console.log('当前标签页URL:', tab.url);

        // 检查URL中是否包含指定内容
        if (tab.url.includes(urlContent)) {
            console.log('URL包含指定内容，刷新页面');
            // 刷新页面
            await chrome.tabs.reload(tab.id);
            sendResponse('check_url:success;');
        } else {
            console.log('URL不包含指定内容');
            sendResponse('check_url:not_found;');
        }
    } catch (error) {
        console.error('处理 check_url 异常:', error);
        sendResponse('check_url:error;');
    }
}

// 处理 click_element 命令
async function handleClickElement(params) {
    try {
        // 参数格式: mode,id
        const parts = params.split(',');
        if (parts.length !== 2) {
            sendResponse('click_element:error:invalid_params;');
            return;
        }

        const mode = parts[0].trim();
        const elementId = parts[1].trim();

        console.log('点击元素 - 模式:', mode, 'ID:', elementId);

        // 获取当前活跃标签页
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (!tab) {
            sendResponse('click_element:error:no_active_tab;');
            return;
        }

        // 等待页面加载完成
        await waitForPageLoad(tab.id);

        // 执行点击操作
        const result = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: clickElementInPage,
            args: [mode, elementId]
        });

        if (result && result[0] && result[0].result) {
            console.log('点击成功');
            sendResponse('click_element:success;');
        } else {
            console.log('点击失败：元素未找到');
            sendResponse('click_element:error:element_not_found;');
        }
    } catch (error) {
        console.error('处理 click_element 异常:', error);
        sendResponse('click_element:error;');
    }
}

// 在页面中查找并点击元素
function clickElementInPage(mode, elementId) {
    let element;

    if (mode === 'class') {
        // 通过 class 查找
        element = document.querySelector(`.${elementId}`);
    } else if (mode === 'id') {
        // 通过 id 查找
        element = document.querySelector(`#${elementId}`);
    } else {
        console.error('未知的查找模式:', mode);
        return false;
    }

    if (element) {
        element.click();
        return true;
    } else {
        console.error('未找到元素:', elementId);
        return false;
    }
}

// 等待页面加载完成
async function waitForPageLoad(tabId) {
    return new Promise((resolve) => {
        // 检查页面加载状态
        chrome.tabs.get(tabId, (tab) => {
            if (tab.status === 'complete') {
                console.log('页面已加载完成');
                resolve();
            } else {
                console.log('等待页面加载...');
                // 监听状态更新
                const listener = (updatedTabId, changeInfo) => {
                    if (updatedTabId === tabId && changeInfo.status === 'complete') {
                        chrome.tabs.onUpdated.removeListener(listener);
                        console.log('页面加载完成');
                        resolve();
                    }
                };
                chrome.tabs.onUpdated.addListener(listener);

                // 设置超时，最多等待10秒
                setTimeout(() => {
                    chrome.tabs.onUpdated.removeListener(listener);
                    console.log('页面加载超时，继续执行');
                    resolve();
                }, 10000);
            }
        });
    });
}

// 处理 open_url 命令
async function handleOpenUrl(url) {
    try {
        console.log('打开新标签页:', url);

        // 创建新标签页并设为活跃
        const newTab = await chrome.tabs.create({
            url: url,
            active: true
        });

        console.log('新标签页已创建，ID:', newTab.id);

        // 获取所有标签页
        const allTabs = await chrome.tabs.query({});

        // 关闭除新标签页外的所有标签页
        for (const tab of allTabs) {
            if (tab.id !== newTab.id) {
                await chrome.tabs.remove(tab.id);
            }
        }

        console.log('已清理其他标签页');
        sendResponse('open_url:success;');
    } catch (error) {
        console.error('处理 open_url 异常:', error);
        sendResponse('open_url:error;');
    }
}

// 插件安装或更新时启动 WebSocket 连接
chrome.runtime.onInstalled.addListener(() => {
    console.log('插件已安装/更新，启动 WebSocket 连接');
    connectWebSocket();
});

// 浏览器启动时启动 WebSocket 连接
chrome.runtime.onStartup.addListener(() => {
    console.log('浏览器启动，启动 WebSocket 连接');
    connectWebSocket();
});