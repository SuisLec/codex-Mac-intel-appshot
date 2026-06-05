import os
import sys
import json
import struct
import shutil
import fnmatch
import tempfile
import subprocess

def extract_asar(asar_path, dest_dir):
    with open(asar_path, "rb") as f:
        header_meta = f.read(16)
        header_size = struct.unpack('<I', header_meta[12:16])[0]
        aligned_size = (header_size + 3) & ~3
        header_json = f.read(header_size).decode('utf-8')
        header = json.loads(header_json)
        payload_start = 16 + aligned_size
        
        def extract_node(node, current_path):
            if "files" in node:
                os.makedirs(current_path, exist_ok=True)
                for name, child in node["files"].items():
                    extract_node(child, os.path.join(current_path, name))
            else:
                if node.get("unpacked"):
                    return
                size = node["size"]
                offset = int(node["offset"])
                f.seek(payload_start + offset)
                data = f.read(size)
                os.makedirs(os.path.dirname(current_path), exist_ok=True)
                with open(current_path, "wb") as out:
                    out.write(data)
        
        extract_node(header, dest_dir)

def pack_asar(original_asar_path, extracted_dir, output_asar_path):
    with open(original_asar_path, "rb") as f:
        header_meta = f.read(16)
        header_size = struct.unpack('<I', header_meta[12:16])[0]
        header_json = f.read(header_size).decode('utf-8')
        header = json.loads(header_json)
    
    payload = bytearray()
    
    def process_node(node, rel_path):
        if "files" in node:
            for name, child in list(node["files"].items()):
                process_node(child, os.path.join(rel_path, name) if rel_path else name)
        else:
            if node.get("unpacked"):
                return
            filepath = os.path.join(extracted_dir, rel_path)
            if not os.path.exists(filepath):
                return
            with open(filepath, "rb") as f_in:
                data = f_in.read()
            node["size"] = len(data)
            node["offset"] = str(len(payload))
            payload.extend(data)
            if "integrity" in node:
                del node["integrity"]
    
    process_node(header, "")
    new_header_json = json.dumps(header, separators=(',', ':')).encode('utf-8')
    new_header_size = len(new_header_json)
    aligned_header_size = (new_header_size + 3) & ~3
    padding_size = aligned_header_size - new_header_size
    padding = b"\x00" * padding_size
    
    with open(output_asar_path, "wb") as f_out:
        f_out.write(struct.pack('<I', 4))
        f_out.write(struct.pack('<I', aligned_header_size + 8))
        f_out.write(struct.pack('<I', aligned_header_size + 4))
        f_out.write(struct.pack('<I', new_header_size))
        f_out.write(new_header_json)
        f_out.write(padding)
        f_out.write(payload)

def compile_swift_files(src_dir, dest_dir):
    files = ["get_window_id", "get_ax_text", "get_frontmost_window"]
    for file in files:
        src = os.path.join(src_dir, f"{file}.swift")
        out = os.path.join(dest_dir, file)
        subprocess.run(["swiftc", src, "-o", out], check=True)

def find_file(directory, pattern):
    for root, _, files in os.walk(directory):
        for f in files:
            if fnmatch.fnmatch(f, pattern):
                return os.path.join(root, f)
    return None

def patch_worker_js(worker_path, helper_dir):
    with open(worker_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    start_marker = "case`computer-use-capture`:return{computerUseCapture:{"
    start_idx = content.find(start_marker)
    if start_idx == -1:
        raise ValueError("Worker start marker not found")
        
    git_marker = "case`git`:return{git:{createWorkerRpcClient:"
    git_idx = content.find(git_marker, start_idx)
    if git_idx == -1:
        raise ValueError("Worker git marker not found")
        
    end_idx_suffix = content.find("}}}}", git_idx)
    if end_idx_suffix == -1:
        raise ValueError("Worker suffix not found")
    end_idx_full = end_idx_suffix + 4
    
    git_block = content[git_idx:end_idx_full]
    
    mock_block = f"""case`computer-use-capture`:return{{computerUseCapture:{{
  getNextCaptureUpdate: async (params) => {{
    const {{ requestId }} = params;
    const fs = require('fs');
    const os = require('os');
    const path = require('path');
    
    global._captureStates = global._captureStates || {{}};
    const state = global._captureStates[requestId] || 0;
    
    const tmpDir = path.join(os.tmpdir(), "com.openai.sky.CUAService");
    const screenshotPath = path.join(tmpDir, `${{requestId}}.jpg`);
    
    const app = (global._captureApps || {{}})[requestId] || "com.apple.finder";
    const axText = (global._captureAxTexts || {{}})[requestId] || "";
    
    if (state === 0) {{
      global._captureStates[requestId] = 1;
      return {{ type: "metadata", app: {{ bundleIdentifier: app }} }};
    }} else if (state === 1) {{
      global._captureStates[requestId] = 2;
      return {{ type: "axText", text: axText }};
    }} else if (state === 2) {{
      global._captureStates[requestId] = 3;
      let base64Data = "";
      try {{
        if (fs.existsSync(screenshotPath)) {{
          const data = fs.readFileSync(screenshotPath);
          base64Data = data.toString("base64");
        }}
      }} catch (e) {{}}
      
      const dataUrl = "data:image/jpeg;base64," + base64Data;
      global._captureDataUrls = global._captureDataUrls || {{}};
      global._captureDataUrls[requestId] = dataUrl;
      
      return {{
        type: "screenshot",
        screenshotPath: screenshotPath,
        screenshotDataURL: dataUrl
      }};
    }} else {{
      delete global._captureStates[requestId];
      if (global._captureApps) delete global._captureApps[requestId];
      if (global._captureAxTexts) delete global._captureAxTexts[requestId];
      
      const dataUrl = (global._captureDataUrls || {{}})[requestId] || null;
      if (global._captureDataUrls) {{
        delete global._captureDataUrls[requestId];
      }}
      return {{
        type: "completed",
        transitionSnapshotPath: null,
        transitionSnapshotDataURL: dataUrl
      }};
    }}
  }},
  startCapture: async (params) => {{
    const {{ animationTarget, app, requestId }} = params;
    const fs = require('fs');
    const os = require('os');
    const path = require('path');
    const child_process = require('child_process');
    
    global._captureApps = global._captureApps || {{}};
    global._captureApps[requestId] = app || "com.apple.finder";
    
    const tmpDir = path.join(os.tmpdir(), "com.openai.sky.CUAService");
    if (!fs.existsSync(tmpDir)) {{
      fs.mkdirSync(tmpDir, {{ recursive: true }});
    }}
    const screenshotPath = path.join(tmpDir, `${{requestId}}.jpg`);
    
    let windowId = "";
    if (app && app.trim().length > 0) {{
      try {{
        const cmd = `"{helper_dir}/get_window_id" "${{app}}"`;
        windowId = child_process.execSync(cmd, {{ encoding: "utf-8" }}).trim();
      }} catch (e) {{}}
    }}
    
    let axText = "";
    if (app && app.trim().length > 0) {{
      try {{
        const cmd = `"{helper_dir}/get_ax_text" "${{app}}"`;
        axText = child_process.execSync(cmd, {{ encoding: "utf-8" }}).trim();
      }} catch (e) {{}}
    }}
    global._captureAxTexts = global._captureAxTexts || {{}};
    global._captureAxTexts[requestId] = axText;
    
    let captureCmd = "";
    if (windowId && windowId.length > 0) {{
      captureCmd = `screencapture -l ${{windowId}} -o -t jpg "${{screenshotPath}}" && sips -s format jpeg -s formatOptions 85 --resampleWidth 2048 "${{screenshotPath}}" --out "${{screenshotPath}}"`;
    }} else {{
      captureCmd = `screencapture -x -t jpg "${{screenshotPath}}" && sips -s format jpeg -s formatOptions 85 --resampleWidth 2048 "${{screenshotPath}}" --out "${{screenshotPath}}"`;
    }}
    
    try {{
      child_process.execSync(captureCmd, {{ stdio: ["pipe", "pipe", "pipe"] }});
    }} catch (e) {{
      const stderr = e.stderr ? e.stderr.toString() : "";
      if (stderr.includes("could not create image") || e.message.includes("could not create image")) {{
        try {{
          child_process.execSync('open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"');
        }} catch(openErr) {{}}
      }}
    }}
    
    global._captureStates = global._captureStates || {{}};
    global._captureStates[requestId] = 0;
    
    return {{
      animationDuration: 0.0,
      transitionSnapshotHeight: null,
      transitionSpringDampingFraction: null,
      transitionSpringResponse: null
    }};
  }}
}}}}"""
    
    new_content = content[:start_idx] + mock_block + git_block + content[end_idx_full:]
    with open(worker_path, "w", encoding="utf-8") as f:
        f.write(new_content)

def patch_main_js(main_path, helper_dir):
    with open(main_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    replacement = f""""computer-use-frontmost-window":async()=>{{
  try {{
    const cp = require('child_process');
    const out = cp.execSync('"{helper_dir}/get_frontmost_window"', {{ encoding: 'utf-8' }}).trim();
    return JSON.parse(out);
  }} catch(e) {{
    return null;
  }}
}},"""

    target = '"computer-use-frontmost-window":async()=>process.platform===`darwin`?Wc():null,'
    if target in content:
        new_content = content.replace(target, replacement)
    else:
        import re
        pattern = r'"computer-use-frontmost-window":async\(\)=>\{.*?return null;\s*\}\s*\},'
        new_content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)
        if count == 0:
            pattern_generic = r'"computer-use-frontmost-window":async\(\)=>\{.*?\},'
            new_content, count = re.subn(pattern_generic, replacement, content, flags=re.DOTALL)
            if count == 0:
                raise ValueError("Main frontmost-window target not found")
        
    with open(main_path, "w", encoding="utf-8") as f:
        f.write(new_content)

def patch_composer_js(composer_path):
    with open(composer_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    target = 're=r.map((e,t)=>{let i=e.imageDataUrl??e.imagePath;return i==null?null:(0,Q.jsx)(Is,{screenshotSrc:i,transitionSnapshotSrc:e.transitionSnapshotDataUrl,transitionSnapshotHeight:e.transitionSnapshotHeight,appName:e.appName,accessibilityText:e.axTree,windowTitle:e.windowTitle,previewEnabled:f,previewIndex:n.length+r.slice(0,t).filter(Sf).length,previewItems:m,onRemove:()=>l(t)},`${e.bundleIdentifier}-${e.imageName??t}`)})'
    replacement = 're=r.map((e,t)=>{let i=e.imageDataUrl??e.imagePath;return i==null?null:(0,Q.jsx)(Is,{screenshotSrc:i,transitionSnapshotSrc:e.transitionSnapshotDataUrl,transitionSnapshotHeight:e.transitionSnapshotHeight,appName:e.appName,accessibilityText:e.axTree,windowTitle:e.windowTitle,previewEnabled:f,previewIndex:n.length+r.slice(0,t).filter(Sf).length,previewItems:m,onRemove:()=>l(t),variant:"thread",appIconSrc:e.appIconDataUrl},`${e.bundleIdentifier}-${e.imageName??t}`)})'
    
    if target in content:
        new_content = content.replace(target, replacement)
    elif replacement in content:
        return
    else:
        raise ValueError("Composer rendering target not found")
        
    with open(composer_path, "w", encoding="utf-8") as f:
        f.write(new_content)

def main():
    app_path = "/Applications/Codex.app"
    if not os.path.exists(app_path):
        app_path = os.path.expanduser("~/Applications/Codex.app")
    if not os.path.exists(app_path):
        print(f"Error: Codex.app not found at {app_path}")
        sys.exit(1)
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bin_dir = os.path.join(app_path, "Contents/Resources/bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    print("Compiling Swift helpers...")
    compile_swift_files(script_dir, bin_dir)
    print("Swift helpers compiled successfully.")
    
    asar_path = os.path.join(app_path, "Contents/Resources/app.asar")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print("Extracting app.asar...")
        extract_meta = os.path.join(temp_dir, "extract")
        extract_asar(asar_path, extract_meta)
        print("Extraction complete.")
        
        worker_path = find_file(os.path.join(extract_meta, ".vite/build"), "worker.js")
        main_path = find_file(os.path.join(extract_meta, ".vite/build"), "main-*.js")
        if not main_path:
            main_path = find_file(os.path.join(extract_meta, ".vite/build"), "main.js")
            
        composer_path = None
        for root, _, files in os.walk(os.path.join(extract_meta, "webview")):
            for f in files:
                if f.startswith("composer-") and f.count("-") == 1 and f.endswith(".js"):
                    composer_path = os.path.join(root, f)
                    break
            if composer_path:
                break
        if not composer_path:
            composer_path = find_file(os.path.join(extract_meta, "webview"), "composer.js")
            
        if not worker_path or not main_path or not composer_path:
            print("Error: Could not locate built JavaScript assets inside app.asar.")
            sys.exit(1)
            
        print("Patching worker.js...")
        patch_worker_js(worker_path, bin_dir)
        
        print("Patching main.js...")
        patch_main_js(main_path, bin_dir)
        
        print("Patching composer.js...")
        patch_composer_js(composer_path)
        
        temp_asar = os.path.join(script_dir, "temp_app.asar")
        print("Packing modified app.asar...")
        pack_asar(asar_path, extract_meta, temp_asar)
        
        print("Replacing app.asar...")
        shutil.copy(temp_asar, asar_path)
        os.remove(temp_asar)
        
    print("Resigning Codex.app...")
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", app_path], check=True)
    
    print("Resetting TCC privacy database for Screen Capture and Accessibility...")
    subprocess.run(["tccutil", "reset", "ScreenCapture", "com.openai.codex"])
    subprocess.run(["tccutil", "reset", "Accessibility", "com.openai.codex"])
    
    print("Successfully completed! Please restart Codex.app.")

if __name__ == "__main__":
    main()
