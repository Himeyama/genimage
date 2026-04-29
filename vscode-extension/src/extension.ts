import * as vscode from 'vscode';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

let mcpClient: Client | undefined;
let transport: StdioClientTransport | undefined;
let activeProvider: GenImageSidebarProvider | undefined;

function getServerCwd(context: vscode.ExtensionContext): string {
    const config = vscode.workspace.getConfiguration('genimage');
    let cwd = config.get<string>('mcpServerCwd') || '${workspaceFolder}';

    if (cwd.includes('${workspaceFolder}')) {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (workspaceFolders && workspaceFolders.length > 0) {
            cwd = cwd.replace('${workspaceFolder}', workspaceFolders[0].uri.fsPath);
        } else {
            cwd = vscode.Uri.joinPath(context.extensionUri, '..').fsPath;
        }
    }
    return cwd;
}

function stopClient() {
    if (mcpClient) {
        try { mcpClient.close(); } catch (e) {}
        mcpClient = undefined;
    }
    if (transport) {
        try { transport.close(); } catch (e) {}
        transport = undefined;
    }
    console.log("MCP Server stopped.");
}

async function initClient(context: vscode.ExtensionContext, uiModelPath?: string): Promise<Client> {
    if (mcpClient && transport) {
        return mcpClient;
    }

    const config = vscode.workspace.getConfiguration('genimage');
    const serverPath = config.get<string>('mcpServerPath') || 'uv';
    const serverArgs = config.get<string[]>('mcpServerArgs') || ['run', 'main.py', '--mcp'];
    const modelPath = uiModelPath !== undefined ? uiModelPath : (config.get<string>('modelPath') || '');
    const cwd = getServerCwd(context);

    if (!serverPath) {
        throw new Error('MCP Server Path is empty');
    }

    const env = { ...(process.env as any) };
    if (modelPath.trim()) {
        env['MODEL'] = modelPath.trim();
        // UIでの変更を永続化（任意）
        config.update('modelPath', modelPath.trim(), vscode.ConfigurationTarget.Workspace).then(undefined, e => console.error(e));
    }

    transport = new StdioClientTransport({
        command: serverPath,
        args: serverArgs,
        cwd: cwd,
        env: env,
        stderr: 'pipe'
    });

    let pythonStderr = '';
    if (transport.stderr) {
        transport.stderr.on('data', (chunk) => {
            const msg = chunk.toString();
            pythonStderr += msg;
            console.error('[MCP Error]', msg);
        });
    }

    mcpClient = new Client(
        {
            name: 'genimage-vscode-client',
            version: '0.1.0',
        },
        { capabilities: {} }
    );

    transport.onclose = () => {
        mcpClient = undefined;
        transport = undefined;
        console.log("MCP Transport closed.");
        
        if (activeProvider && activeProvider.getView()) {
             activeProvider.getView()!.webview.postMessage({ command: 'serverStatus', status: 'stopped' });
        }

        if (pythonStderr.trim()) {
            vscode.window.showErrorMessage(`MCPプロセスが終了しました。エラー:\n${pythonStderr}`);
        } else {
             vscode.window.showWarningMessage(`MCPプロセスが切断されました。`);
        }
    };
    
    transport.onerror = (error) => {
        console.error("MCP Transport error:", error);
    };

    await mcpClient.connect(transport);
    
    if (activeProvider && activeProvider.getView()) {
         activeProvider.getView()!.webview.postMessage({ command: 'serverStatus', status: 'running' });
    }

    return mcpClient;
}

export function activate(context: vscode.ExtensionContext) {
    activeProvider = new GenImageSidebarProvider(context);
    
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(GenImageSidebarProvider.viewType, activeProvider)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('genimage.focusSidebar', () => {
            vscode.commands.executeCommand('genimage.sidebar.focus');
        })
    );
}

class GenImageSidebarProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'genimage.sidebar';
    private _view?: vscode.WebviewView;

    constructor(
        private readonly _context: vscode.ExtensionContext,
    ) { }

    public getView() {
        return this._view;
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;

        const cwdUri = vscode.Uri.file(getServerCwd(this._context));
        const workspaceFolders = vscode.workspace.workspaceFolders || [];
        const localResourceRoots = [cwdUri, ...workspaceFolders.map(f => f.uri)];

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: localResourceRoots
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        const config = vscode.workspace.getConfiguration('genimage');
        const initialModelPath = config.get<string>('modelPath') || '';
        webviewView.webview.postMessage({ command: 'initSettings', modelPath: initialModelPath });

        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.command) {
                case 'generate':
                    await this._handleGenerate(message.data, message.msgId);
                    return;
                case 'pickImage':
                    const uri = await vscode.window.showOpenDialog({
                        canSelectMany: false,
                        openLabel: 'Select Input Image',
                        filters: { 'Images': ['png', 'jpg', 'jpeg', 'webp'] }
                    });
                    if (uri && uri[0]) {
                        webviewView.webview.postMessage({ command: 'imagePicked', path: uri[0].fsPath });
                    }
                    return;
                case 'pickModel':
                    const modelUri = await vscode.window.showOpenDialog({
                        canSelectMany: false,
                        openLabel: 'Select Model',
                        filters: { 'Models': ['safetensors', 'ckpt', 'bin'] }
                    });
                    if (modelUri && modelUri[0]) {
                        webviewView.webview.postMessage({ command: 'modelPicked', path: modelUri[0].fsPath });
                    }
                    return;
                case 'error':
                    vscode.window.showErrorMessage(message.text);
                    return;
                case 'startServer':
                    try {
                        this._view!.webview.postMessage({ command: 'serverStatus', status: 'starting' });
                        await initClient(this._context, message.modelPath);
                    } catch (e: any) {
                        vscode.window.showErrorMessage('サーバーの起動に失敗しました: ' + e.message);
                        this._view!.webview.postMessage({ command: 'serverStatus', status: 'stopped' });
                    }
                    return;
                case 'stopServer':
                    stopClient();
                    this._view!.webview.postMessage({ command: 'serverStatus', status: 'stopped' });
                    return;
                case 'checkServerStatus':
                    this._view!.webview.postMessage({ 
                        command: 'serverStatus', 
                        status: (mcpClient && transport) ? 'running' : 'stopped' 
                    });
                    return;
            }
        });
    }

    private async _handleGenerate(data: any, msgId: string) {
        if (!this._view) return;
        
        this._view.webview.postMessage({ command: 'status', msgId: msgId, text: 'MCPサーバーに接続中...' });

        try {
            const client = await initClient(this._context);
            this._view.webview.postMessage({ command: 'status', msgId: msgId, text: '画像生成中...' });

            const cwd = getServerCwd(this._context);
            const defaultOutputPath = vscode.Uri.joinPath(vscode.Uri.file(cwd), 'images', `vscode-output-${Date.now()}.png`).fsPath;

            let result: any;
            if (data.mode === 'txt2img') {
                result = (await client.callTool({
                    name: 'generate_image',
                    arguments: {
                        prompt: data.prompt,
                        negative_prompt: data.negativePrompt || undefined,
                        steps: data.steps,
                        output_path: defaultOutputPath
                    }
                })) as any;
            } else if (data.mode === 'img2img') {
                result = (await client.callTool({
                    name: 'image2image',
                    arguments: {
                        prompt: data.prompt,
                        image_path: data.imagePath,
                        negative_prompt: data.negativePrompt || undefined,
                        strength: data.strength,
                        steps: data.steps,
                        output_path: defaultOutputPath
                    }
                })) as any;
            }

            if (result && result.content && result.content.length > 0) {
                const content = result.content[0] as any;
                if (content.type === 'text') {
                    const parsed = JSON.parse(content.text);
                    if (parsed.success && parsed.output) {
                        const fileUri = vscode.Uri.file(parsed.output);
                        const webviewUri = this._view.webview.asWebviewUri(fileUri);
                        
                        console.log("Resolved Image URI for Webview:", webviewUri.toString());
                        
                        const previewUrl = webviewUri.toString() + '?t=' + Date.now();
                        
                        this._view.webview.postMessage({ 
                            command: 'result', 
                            msgId: msgId,
                            success: true, 
                            url: previewUrl,
                            localPath: parsed.output
                        });
                    } else {
                        this._view.webview.postMessage({ command: 'result', msgId: msgId, success: false, error: parsed.message });
                    }
                }
            } else {
                this._view.webview.postMessage({ command: 'result', msgId: msgId, success: false, error: 'サーバーから不正なレスポンスが返されました。' });
            }
        } catch (error: any) {
            this._view.webview.postMessage({ command: 'result', msgId: msgId, success: false, error: error.message });
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        // CSPで webview のリソースURI (vscode-resource: など) を許可する
        const cspSource = webview.cspSource;
        return `<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${cspSource} https:; script-src 'unsafe-inline'; style-src 'unsafe-inline';">
    <title>GenImage Studio</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            background-color: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            height: 100vh;
            box-sizing: border-box;
            overflow: hidden;
        }

        /* Top Settings Bar */
        .settings-bar {
            padding: 10px 15px;
            background: var(--vscode-editorWidget-background);
            border-bottom: 1px solid var(--vscode-widget-border);
            display: flex;
            flex-direction: column;
            gap: 10px;
            flex-shrink: 0;
        }

        .server-control {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
        }
        .status-stopped { background-color: var(--vscode-testing-iconFailed); }
        .status-running { background-color: var(--vscode-testing-iconPassed); }
        .status-starting { background-color: var(--vscode-testing-iconQueued); animation: pulse 1s infinite alternate; }
        
        @keyframes pulse { 0% { opacity: 0.5; } 100% { opacity: 1; } }
        
        .server-btn {
            padding: 4px 8px;
            font-size: 11px;
            border-radius: 2px;
            cursor: pointer;
            border: none;
            color: var(--vscode-button-foreground);
        }
        .btn-start { background-color: var(--vscode-button-background); }
        .btn-start:hover { background-color: var(--vscode-button-hoverBackground); }
        .btn-stop { background-color: var(--vscode-errorForeground); color: white; }
        .btn-stop:hover { opacity: 0.8; }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        .form-group-row {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        label {
            font-weight: 600;
            font-size: 12px;
            color: var(--vscode-foreground);
        }
        input[type="text"], input[type="number"], textarea, select {
            width: 100%;
            padding: 6px;
            box-sizing: border-box;
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border: 1px solid var(--vscode-input-border);
            border-radius: 4px;
            font-family: var(--vscode-font-family);
            font-size: 12px;
        }
        input[type="text"]:focus, input[type="number"]:focus, textarea:focus, select:focus {
            outline: 1px solid var(--vscode-focusBorder);
            border-color: var(--vscode-focusBorder);
        }

        /* Middle Chat Area */
        .chat-area {
            flex: 1;
            padding: 15px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 15px;
            background-color: var(--vscode-editor-background);
        }

        .chat-message {
            display: flex;
            flex-direction: column;
            max-width: 90%;
        }
        .chat-message.user {
            align-self: flex-end;
            align-items: flex-end;
        }
        .chat-message.assistant {
            align-self: center;
            align-items: center;
            width: 100%;
        }

        .chat-bubble {
            padding: 10px;
            border-radius: 8px;
            font-size: 12px;
            line-height: 1.4;
            word-wrap: break-word;
        }
        .chat-message.user .chat-bubble {
            background-color: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border-bottom-right-radius: 0;
        }
        
        .chat-message.assistant .chat-bubble {
            background-color: transparent;
            padding: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            width: 100%;
            text-align: center;
        }
        
        .chat-details {
            font-size: 11px;
            opacity: 0.8;
            margin-top: 4px;
            white-space: pre-wrap;
        }

        .generated-image {
            max-width: 100%;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            cursor: pointer;
            transition: transform 0.2s;
            display: block;
            margin: 0 auto;
        }
        .generated-image:hover {
            transform: scale(1.02);
        }

        .loader {
            border: 3px solid rgba(255,255,255,0.1);
            border-top: 3px solid var(--vscode-button-background);
            border-radius: 50%;
            width: 20px;
            height: 20px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px auto;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        /* Bottom Input Area */
        .input-area {
            padding: 10px 15px;
            background: var(--vscode-editorWidget-background);
            border-top: 1px solid var(--vscode-widget-border);
            display: flex;
            flex-direction: column;
            gap: 10px;
            flex-shrink: 0;
        }

        textarea {
            resize: vertical;
            min-height: 40px;
        }
        
        .form-group-row label {
            white-space: nowrap;
        }
        
        .btn-primary {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 8px 12px;
            cursor: pointer;
            width: 100%;
            font-weight: 600;
            border-radius: 4px;
            transition: background 0.2s;
            font-size: 12px;
        }
        .btn-primary:hover { background: var(--vscode-button-hoverBackground); }
        .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

        .btn-secondary {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: none;
            padding: 4px 8px;
            cursor: pointer;
            border-radius: 4px;
            font-size: 11px;
        }
        .btn-secondary:hover { background: var(--vscode-button-secondaryHoverBackground); }

        .img2img-only { display: none; }
        
        .error-text { color: var(--vscode-errorForeground); font-size: 12px; }
    </style>
</head>
<body>
    <!-- Top Settings -->
    <div class="settings-bar">
        <div class="server-control">
            <div>
                <span id="serverIndicator" class="status-dot status-stopped"></span>
                <span id="serverLabel" style="font-size: 12px; font-weight: bold;">サーバー: 停止中</span>
            </div>
            <button id="toggleServerBtn" class="server-btn btn-start" style="width: auto;">起動</button>
        </div>

        <div class="form-group-row">
            <label style="flex-shrink: 0;">モデル</label>
            <input type="text" id="modelPathUI" placeholder="HuggingFace ID / ローカルパス" style="flex: 1;" />
            <button type="button" id="pickModelBtn" class="btn-secondary" style="flex-shrink: 0;">参照</button>
        </div>

        <div class="form-group-row">
            <label style="flex-shrink: 0;">モード</label>
            <select id="mode" style="flex: 1;">
                <option value="txt2img">Text to Image (テキストから画像生成)</option>
                <option value="img2img">Image to Image (画像から画像生成)</option>
            </select>
        </div>
    </div>

    <!-- Middle Chat Area -->
    <div class="chat-area" id="chatArea">
    </div>

    <!-- Bottom Input Area -->
    <div class="input-area">
        <div class="form-group">
            <textarea id="prompt" placeholder="プロンプトを入力 (a cute cat, highly detailed...)"></textarea>
        </div>

        <div class="form-group">
            <textarea id="negativePrompt" placeholder="ネガティブプロンプト (オプション)"></textarea>
        </div>

        <div style="display: flex; gap: 10px; align-items: center;">
            <div class="form-group-row" style="flex: 1;">
                <label>ステップ数</label>
                <input type="number" id="steps" value="40" min="1" max="150" />
            </div>
            <div class="form-group-row img2img-only" style="flex: 1;">
                <label>変換強度</label>
                <input type="number" id="strength" value="0.1" step="0.05" min="0.01" max="1.0" />
            </div>
        </div>

        <div class="form-group-row img2img-only">
            <label>入力画像</label>
            <button type="button" id="pickImageBtn" class="btn-secondary">選択</button>
            <div id="pathDisplay" style="font-size: 10px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">未選択</div>
            <input type="hidden" id="imagePath" />
        </div>

        <button id="generateBtn" class="btn-primary">画像を生成</button>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        
        const toggleServerBtn = document.getElementById('toggleServerBtn');
        const serverIndicator = document.getElementById('serverIndicator');
        const serverLabel = document.getElementById('serverLabel');
        let currentServerState = 'stopped';

        const modeSelect = document.getElementById('mode');
        const img2imgSections = document.querySelectorAll('.img2img-only');
        const pickImageBtn = document.getElementById('pickImageBtn');
        const pickModelBtn = document.getElementById('pickModelBtn');
        const generateBtn = document.getElementById('generateBtn');
        const imagePathInput = document.getElementById('imagePath');
        const pathDisplay = document.getElementById('pathDisplay');
        const modelPathUI = document.getElementById('modelPathUI');
        const chatArea = document.getElementById('chatArea');

        let currentMessageId = 0;

        // Request initial server status
        vscode.postMessage({ command: 'checkServerStatus' });

        toggleServerBtn.addEventListener('click', () => {
            if (currentServerState === 'stopped') {
                vscode.postMessage({ command: 'startServer', modelPath: modelPathUI.value.trim() });
            } else if (currentServerState === 'running') {
                vscode.postMessage({ command: 'stopServer' });
            }
        });

        modeSelect.addEventListener('change', (e) => {
            const isImg2Img = e.target.value === 'img2img';
            img2imgSections.forEach(el => el.style.display = isImg2Img ? 'flex' : 'none');
        });

        pickImageBtn.addEventListener('click', () => {
            vscode.postMessage({ command: 'pickImage' });
        });

        pickModelBtn.addEventListener('click', () => {
            vscode.postMessage({ command: 'pickModel' });
        });

        function appendUserMessage(prompt, negativePrompt, steps, mode, strength, imgPath) {
            const msgDiv = document.createElement('div');
            msgDiv.className = 'chat-message user';
            
            let details = \`ステップ数: \${steps}\`;
            if (mode === 'img2img') {
                details += \` | 変換強度: \${strength}\`;
            }
            if (negativePrompt) {
                details += \`\\nNP: \${negativePrompt}\`;
            }

            msgDiv.innerHTML = \`
                <div class="chat-bubble">
                    \${prompt}
                    <div class="chat-details">\${details}</div>
                </div>
            \`;
            chatArea.appendChild(msgDiv);
            scrollToBottom();
        }

        function appendAssistantLoader() {
            currentMessageId++;
            const msgId = 'msg-' + currentMessageId;
            const msgDiv = document.createElement('div');
            msgDiv.className = 'chat-message assistant';
            msgDiv.id = msgId;
            
            msgDiv.innerHTML = \`
                <div class="chat-bubble">
                    <div class="loader"></div>
                    <div class="status-text" id="status-\${msgId}">準備中...</div>
                </div>
            \`;
            chatArea.appendChild(msgDiv);
            scrollToBottom();
            return msgId;
        }

        function updateAssistantMessage(msgId, success, urlOrError, localPath) {
            const msgDiv = document.getElementById(msgId);
            if (!msgDiv) return;

            const bubble = msgDiv.querySelector('.chat-bubble');
            if (success) {
                bubble.innerHTML = \`
                    <img src="\${urlOrError}" class="generated-image" style="display: block;" title="\${localPath} (クリックで開く)" onclick="window.open('\${urlOrError}')" />
                    <div style="font-size: 10px; color: var(--vscode-descriptionForeground); margin-top: 4px;">保存先: \${localPath.split(/\\\\|\\//).pop()}</div>
                \`;
            } else {
                bubble.innerHTML = \`<div class="error-text">エラー: \${urlOrError}</div>\`;
            }
            scrollToBottom();
        }

        function updateAssistantStatus(msgId, text) {
            const statusText = document.getElementById(\`status-\${msgId}\`);
            if (statusText) {
                statusText.textContent = text;
            }
        }

        function scrollToBottom() {
            chatArea.scrollTop = chatArea.scrollHeight;
        }

        let activeMessageId = null;

        generateBtn.addEventListener('click', () => {
            const mode = modeSelect.value;
            const prompt = document.getElementById('prompt').value.trim();
            const negativePrompt = document.getElementById('negativePrompt').value.trim();
            const steps = parseInt(document.getElementById('steps').value, 10);
            
            if (!prompt) {
                vscode.postMessage({ command: 'error', text: 'プロンプトを入力してください' });
                return;
            }

            const data = { mode, prompt, negativePrompt, steps };

            if (mode === 'img2img') {
                const imagePath = imagePathInput.value;
                const strength = parseFloat(document.getElementById('strength').value);
                
                if (!imagePath) {
                    vscode.postMessage({ command: 'error', text: 'Image to Image では入力画像が必要です' });
                    return;
                }
                data.imagePath = imagePath;
                data.strength = strength;
            }

            generateBtn.disabled = true;
            appendUserMessage(prompt, negativePrompt, steps, mode, data.strength, data.imagePath);
            activeMessageId = appendAssistantLoader();

            vscode.postMessage({ command: 'generate', data, msgId: activeMessageId });
        });

        window.addEventListener('message', event => {
            const message = event.data;
            switch (message.command) {
                case 'initSettings':
                    if (message.modelPath) {
                        modelPathUI.value = message.modelPath;
                    }
                    break;
                case 'serverStatus':
                    currentServerState = message.status;
                    if (message.status === 'stopped') {
                        serverIndicator.className = 'status-dot status-stopped';
                        serverLabel.textContent = 'サーバー: 停止中';
                        toggleServerBtn.textContent = '起動';
                        toggleServerBtn.className = 'server-btn btn-start';
                        toggleServerBtn.disabled = false;
                    } else if (message.status === 'starting') {
                        serverIndicator.className = 'status-dot status-starting';
                        serverLabel.textContent = 'サーバー: 起動中...';
                        toggleServerBtn.textContent = '...';
                        toggleServerBtn.disabled = true;
                    } else if (message.status === 'running') {
                        serverIndicator.className = 'status-dot status-running';
                        serverLabel.textContent = 'サーバー: 稼働中';
                        toggleServerBtn.textContent = '停止';
                        toggleServerBtn.className = 'server-btn btn-stop';
                        toggleServerBtn.disabled = false;
                    }
                    break;
                case 'imagePicked':
                    imagePathInput.value = message.path;
                    pathDisplay.textContent = message.path.split(/\\\\|\\//).pop();
                    pathDisplay.title = message.path;
                    break;
                case 'modelPicked':
                    modelPathUI.value = message.path;
                    break;
                case 'status':
                    if (message.msgId) {
                        updateAssistantStatus(message.msgId, message.text);
                    }
                    break;
                case 'result':
                    generateBtn.disabled = false;
                    if (message.msgId) {
                        updateAssistantMessage(message.msgId, message.success, message.success ? message.url : message.error, message.localPath);
                    }
                    break;
            }
        });
    </script>
</body>
</html>`;
    }
}

export function deactivate() {
    stopClient();
}
