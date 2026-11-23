#include <windows.h>
// Keep the native probe build gated by Windows CI.
#include <d3d12.h>
#include <d3dcompiler.h>
#include <dxgi1_6.h>
#include <wrl/client.h>

#include <array>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using Microsoft::WRL::ComPtr;

static std::string json_escape(const std::string& value) {
    std::ostringstream out;
    for (unsigned char c : value) {
        switch (c) {
        case '"': out << "\\\""; break;
        case '\\': out << "\\\\"; break;
        case '\b': out << "\\b"; break;
        case '\f': out << "\\f"; break;
        case '\n': out << "\\n"; break;
        case '\r': out << "\\r"; break;
        case '\t': out << "\\t"; break;
        default:
            if (c < 0x20) {
                out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                    << static_cast<unsigned int>(c) << std::dec;
            } else out << static_cast<char>(c);
        }
    }
    return out.str();
}

static std::string narrow(const std::wstring& value) {
    if (value.empty()) return {};
    const int size = WideCharToMultiByte(CP_UTF8, 0, value.c_str(),
        static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    if (size <= 0) return {};
    std::string result(static_cast<size_t>(size), '\0');
    WideCharToMultiByte(CP_UTF8, 0, value.c_str(),
        static_cast<int>(value.size()), result.data(), size, nullptr, nullptr);
    return result;
}

static std::string hr_string(HRESULT hr) {
    std::ostringstream out;
    out << "0x" << std::hex << std::uppercase << static_cast<unsigned long>(hr);
    return out.str();
}

static const char* feature_level_name(D3D_FEATURE_LEVEL level) {
    switch (level) {
    case D3D_FEATURE_LEVEL_12_2: return "12_2";
    case D3D_FEATURE_LEVEL_12_1: return "12_1";
    case D3D_FEATURE_LEVEL_12_0: return "12_0";
    case D3D_FEATURE_LEVEL_11_1: return "11_1";
    case D3D_FEATURE_LEVEL_11_0: return "11_0";
    default: return "unknown";
    }
}

static const char* shader_model_name(D3D_SHADER_MODEL model) {
    switch (model) {
    case D3D_SHADER_MODEL_6_7: return "6_7";
    case D3D_SHADER_MODEL_6_6: return "6_6";
    case D3D_SHADER_MODEL_6_5: return "6_5";
    case D3D_SHADER_MODEL_6_4: return "6_4";
    case D3D_SHADER_MODEL_6_3: return "6_3";
    case D3D_SHADER_MODEL_6_2: return "6_2";
    case D3D_SHADER_MODEL_6_1: return "6_1";
    case D3D_SHADER_MODEL_6_0: return "6_0";
    case D3D_SHADER_MODEL_5_1: return "5_1";
    default: return "unknown";
    }
}

static const char* format_name(DXGI_FORMAT format) {
    switch (format) {
    case DXGI_FORMAT_R8G8B8A8_UNORM: return "R8G8B8A8_UNORM";
    case DXGI_FORMAT_B8G8R8A8_UNORM: return "B8G8R8A8_UNORM";
    case DXGI_FORMAT_R16G16B16A16_FLOAT: return "R16G16B16A16_FLOAT";
    case DXGI_FORMAT_R32_FLOAT: return "R32_FLOAT";
    case DXGI_FORMAT_D32_FLOAT: return "D32_FLOAT";
    case DXGI_FORMAT_BC1_UNORM: return "BC1_UNORM";
    case DXGI_FORMAT_BC7_UNORM: return "BC7_UNORM";
    default: return "UNKNOWN";
    }
}

static std::string query_format_support(ID3D12Device* device, DXGI_FORMAT format) {
    D3D12_FEATURE_DATA_FORMAT_SUPPORT support{};
    support.Format = format;
    const bool available = SUCCEEDED(device->CheckFeatureSupport(
        D3D12_FEATURE_FORMAT_SUPPORT, &support, sizeof(support)));
    std::ostringstream out;
    out << "{\"format\":\"" << format_name(format)
        << "\",\"query_available\":" << (available ? "true" : "false")
        << ",\"support1\":";
    if (available) out << support.Support1; else out << "null";
    out << ",\"support2\":";
    if (available) out << support.Support2; else out << "null";
    out << "}";
    return out.str();
}

static bool wait_for_fence(ID3D12Fence* fence, UINT64 value, HANDLE eventHandle) {
    if (fence->GetCompletedValue() >= value) return true;
    if (FAILED(fence->SetEventOnCompletion(value, eventHandle))) return false;
    return WaitForSingleObject(eventHandle, 10000) == WAIT_OBJECT_0;
}

struct ResourceSmokeResult {
    bool success = false;
    std::string note = "not_run";
};

static ResourceSmokeResult run_resource_copy_smoke_test(
    ID3D12Device* device, ID3D12CommandQueue* queue) {
    ResourceSmokeResult result;
    constexpr UINT64 size = 256;
    ComPtr<ID3D12Resource> upload, gpu, readback;
    ComPtr<ID3D12CommandAllocator> allocator;
    ComPtr<ID3D12GraphicsCommandList> list;
    ComPtr<ID3D12Fence> fence;
    HANDLE eventHandle = nullptr;

    auto fail = [&](const char* stage, HRESULT hr) {
        result.note = std::string(stage) + ":" + hr_string(hr);
        if (eventHandle) CloseHandle(eventHandle);
        return result;
    };

    D3D12_RESOURCE_DESC desc{};
    desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    desc.Width = size;
    desc.Height = 1;
    desc.DepthOrArraySize = 1;
    desc.MipLevels = 1;
    desc.SampleDesc.Count = 1;
    desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;

    D3D12_HEAP_PROPERTIES uploadHeap{};
    uploadHeap.Type = D3D12_HEAP_TYPE_UPLOAD;
    uploadHeap.CreationNodeMask = 1;
    uploadHeap.VisibleNodeMask = 1;

    D3D12_HEAP_PROPERTIES defaultHeap{};
    defaultHeap.Type = D3D12_HEAP_TYPE_DEFAULT;
    defaultHeap.CreationNodeMask = 1;
    defaultHeap.VisibleNodeMask = 1;

    D3D12_HEAP_PROPERTIES readbackHeap{};
    readbackHeap.Type = D3D12_HEAP_TYPE_READBACK;
    readbackHeap.CreationNodeMask = 1;
    readbackHeap.VisibleNodeMask = 1;

    HRESULT hr = device->CreateCommittedResource(
        &uploadHeap, D3D12_HEAP_FLAG_NONE, &desc,
        D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(&upload));
    if (FAILED(hr)) return fail("upload", hr);

    hr = device->CreateCommittedResource(
        &defaultHeap, D3D12_HEAP_FLAG_NONE, &desc,
        D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(&gpu));
    if (FAILED(hr)) return fail("default", hr);

    hr = device->CreateCommittedResource(
        &readbackHeap, D3D12_HEAP_FLAG_NONE, &desc,
        D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(&readback));
    if (FAILED(hr)) return fail("readback", hr);

    const D3D12_RANGE noRead{0, 0};
    std::uint8_t* source = nullptr;
    hr = upload->Map(0, &noRead, reinterpret_cast<void**>(&source));
    if (FAILED(hr)) return fail("map_upload", hr);
    for (UINT i = 0; i < size; ++i)
        source[i] = static_cast<std::uint8_t>((i * 37u + 11u) & 255u);
    upload->Unmap(0, nullptr);

    hr = device->CreateCommandAllocator(
        D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&allocator));
    if (FAILED(hr)) return fail("allocator", hr);
    hr = device->CreateCommandList(
        0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator.Get(), nullptr,
        IID_PPV_ARGS(&list));
    if (FAILED(hr)) return fail("command_list", hr);

    list->CopyBufferRegion(gpu.Get(), 0, upload.Get(), 0, size);
    D3D12_RESOURCE_BARRIER barrier{};
    barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Transition.pResource = gpu.Get();
    barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_DEST;
    barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
    list->ResourceBarrier(1, &barrier);
    list->CopyBufferRegion(readback.Get(), 0, gpu.Get(), 0, size);

    hr = list->Close();
    if (FAILED(hr)) return fail("close", hr);
    ID3D12CommandList* commandLists[] = {list.Get()};
    queue->ExecuteCommandLists(1, commandLists);

    hr = device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence));
    if (FAILED(hr)) return fail("fence", hr);
    eventHandle = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    if (!eventHandle) {
        result.note = "event_creation_failed";
        return result;
    }
    hr = queue->Signal(fence.Get(), 1);
    if (FAILED(hr)) return fail("signal", hr);
    if (!wait_for_fence(fence.Get(), 1, eventHandle)) {
        CloseHandle(eventHandle);
        result.note = "fence_wait_failed";
        return result;
    }

    const D3D12_RANGE readRange{0, static_cast<SIZE_T>(size)};
    std::uint8_t* actual = nullptr;
    hr = readback->Map(0, &readRange, reinterpret_cast<void**>(&actual));
    if (FAILED(hr)) return fail("map_readback", hr);

    bool matches = true;
    for (UINT i = 0; i < size; ++i) {
        const auto expected = static_cast<std::uint8_t>((i * 37u + 11u) & 255u);
        if (actual[i] != expected) {
            matches = false;
            break;
        }
    }
    const D3D12_RANGE noWrite{0, 0};
    readback->Unmap(0, &noWrite);
    CloseHandle(eventHandle);

    result.success = matches;
    result.note = matches ? "upload_copy_barrier_readback_verified"
                          : "readback_mismatch";
    return result;
}


struct BindingSmokeResult {
    bool rootSignatureCreated = false;
    bool resourceHeapCreated = false;
    bool samplerHeapCreated = false;
    UINT resourceDescriptorIncrement = 0;
    UINT samplerDescriptorIncrement = 0;
    std::string note = "not_run";
};

static BindingSmokeResult run_binding_smoke_test(ID3D12Device* device) {
    BindingSmokeResult result;
    D3D12_ROOT_SIGNATURE_DESC rootDesc{};
    rootDesc.NumParameters = 0;
    rootDesc.pParameters = nullptr;
    rootDesc.NumStaticSamplers = 0;
    rootDesc.pStaticSamplers = nullptr;
    rootDesc.Flags = D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;

    ComPtr<ID3DBlob> serialized;
    ComPtr<ID3DBlob> errors;
    HRESULT hr = D3D12SerializeRootSignature(
        &rootDesc, D3D_ROOT_SIGNATURE_VERSION_1, &serialized, &errors);
    if (FAILED(hr)) {
        result.note = "root_signature_serialize:" + hr_string(hr);
        return result;
    }
    ComPtr<ID3D12RootSignature> rootSignature;
    hr = device->CreateRootSignature(0, serialized->GetBufferPointer(),
        serialized->GetBufferSize(), IID_PPV_ARGS(&rootSignature));
    if (FAILED(hr)) {
        result.note = "root_signature_create:" + hr_string(hr);
        return result;
    }
    result.rootSignatureCreated = true;

    D3D12_DESCRIPTOR_HEAP_DESC resourceHeapDesc{};
    resourceHeapDesc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
    resourceHeapDesc.NumDescriptors = 16;
    resourceHeapDesc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    hr = device->CreateDescriptorHeap(&resourceHeapDesc, IID_PPV_ARGS(&ComPtr<ID3D12DescriptorHeap>()));
    if (SUCCEEDED(hr)) {
        ComPtr<ID3D12DescriptorHeap> heap;
        hr = device->CreateDescriptorHeap(&resourceHeapDesc, IID_PPV_ARGS(&heap));
        if (SUCCEEDED(hr)) {
            result.resourceHeapCreated = true;
            result.resourceDescriptorIncrement =
                device->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
        }
    }
    if (FAILED(hr)) {
        result.note = "resource_descriptor_heap:" + hr_string(hr);
        return result;
    }

    D3D12_DESCRIPTOR_HEAP_DESC samplerHeapDesc{};
    samplerHeapDesc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER;
    samplerHeapDesc.NumDescriptors = 8;
    samplerHeapDesc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    ComPtr<ID3D12DescriptorHeap> samplerHeap;
    hr = device->CreateDescriptorHeap(&samplerHeapDesc, IID_PPV_ARGS(&samplerHeap));
    if (FAILED(hr)) {
        result.note = "sampler_descriptor_heap:" + hr_string(hr);
        return result;
    }
    result.samplerHeapCreated = true;
    result.samplerDescriptorIncrement =
        device->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER);
    result.note = "empty_root_signature_and_shader_visible_descriptor_heaps_created";
    return result;
}



struct RenderSmokeResult {
    bool success = false;
    bool shaderCompile = false;
    bool rootSignature = false;
    bool pipelineState = false;
    bool drawExecuted = false;
    std::string note = "not_run";
};

static RenderSmokeResult run_render_smoke_test(
    ID3D12Device* device, ID3D12CommandQueue* queue) {
    RenderSmokeResult result;
    constexpr UINT width = 64;
    constexpr UINT height = 64;
    constexpr DXGI_FORMAT targetFormat = DXGI_FORMAT_R8G8B8A8_UNORM;
    ComPtr<ID3DBlob> vertexShader, pixelShader, errors;
    const char* shaderSource =
        "struct VOut { float4 position : SV_Position; };"
        "VOut VSMain(uint id : SV_VertexID) {"
        " float2 p[3] = { float2(-1.0, -1.0), float2(-1.0, 3.0), float2(3.0, -1.0) };"
        " VOut o; o.position = float4(p[id], 0.0, 1.0); return o; }"
        "float4 PSMain() : SV_Target { return float4(1.0, 0.0, 0.0, 1.0); }";
    HRESULT hr = D3DCompile(shaderSource, strlen(shaderSource), "orion_smoke.hlsl",
        nullptr, nullptr, "VSMain", "vs_5_0", D3DCOMPILE_OPTIMIZATION_LEVEL3,
        0, &vertexShader, &errors);
    if (FAILED(hr)) {
        result.note = "vertex_shader_compile:" + hr_string(hr);
        return result;
    }
    hr = D3DCompile(shaderSource, strlen(shaderSource), "orion_smoke.hlsl",
        nullptr, nullptr, "PSMain", "ps_5_0", D3DCOMPILE_OPTIMIZATION_LEVEL3,
        0, &pixelShader, &errors);
    if (FAILED(hr)) {
        result.note = "pixel_shader_compile:" + hr_string(hr);
        return result;
    }
    result.shaderCompile = true;

    D3D12_ROOT_SIGNATURE_DESC rootDesc{};
    rootDesc.Flags = D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;
    ComPtr<ID3DBlob> serializedRoot, rootErrors;
    hr = D3D12SerializeRootSignature(&rootDesc, D3D_ROOT_SIGNATURE_VERSION_1,
        &serializedRoot, &rootErrors);
    if (FAILED(hr)) {
        result.note = "root_signature_serialize:" + hr_string(hr);
        return result;
    }
    ComPtr<ID3D12RootSignature> rootSignature;
    hr = device->CreateRootSignature(0, serializedRoot->GetBufferPointer(),
        serializedRoot->GetBufferSize(), IID_PPV_ARGS(&rootSignature));
    if (FAILED(hr)) {
        result.note = "root_signature_create:" + hr_string(hr);
        return result;
    }
    result.rootSignature = true;

    D3D12_GRAPHICS_PIPELINE_STATE_DESC psoDesc{};
    psoDesc.pRootSignature = rootSignature.Get();
    psoDesc.VS = {vertexShader->GetBufferPointer(), vertexShader->GetBufferSize()};
    psoDesc.PS = {pixelShader->GetBufferPointer(), pixelShader->GetBufferSize()};
    psoDesc.BlendState.AlphaToCoverageEnable = FALSE;
    psoDesc.BlendState.IndependentBlendEnable = FALSE;
    const D3D12_RENDER_TARGET_BLEND_DESC blend = {
        FALSE, FALSE, D3D12_BLEND_ONE, D3D12_BLEND_ZERO, D3D12_BLEND_OP_ADD,
        D3D12_BLEND_ONE, D3D12_BLEND_ZERO, D3D12_BLEND_OP_ADD,
        D3D12_LOGIC_OP_NOOP,
        D3D12_COLOR_WRITE_ENABLE_ALL
    };
    for (auto& target : psoDesc.BlendState.RenderTarget) target = blend;
    psoDesc.SampleMask = UINT_MAX;
    psoDesc.RasterizerState.FillMode = D3D12_FILL_MODE_SOLID;
    psoDesc.RasterizerState.CullMode = D3D12_CULL_MODE_NONE;
    psoDesc.RasterizerState.FrontCounterClockwise = FALSE;
    psoDesc.RasterizerState.DepthBias = D3D12_DEFAULT_DEPTH_BIAS;
    psoDesc.RasterizerState.DepthBiasClamp = D3D12_DEFAULT_DEPTH_BIAS_CLAMP;
    psoDesc.RasterizerState.SlopeScaledDepthBias = D3D12_DEFAULT_SLOPE_SCALED_DEPTH_BIAS;
    psoDesc.RasterizerState.DepthClipEnable = TRUE;
    psoDesc.RasterizerState.MultisampleEnable = FALSE;
    psoDesc.RasterizerState.AntialiasedLineEnable = FALSE;
    psoDesc.RasterizerState.ForcedSampleCount = 0;
    psoDesc.RasterizerState.ConservativeRaster = D3D12_CONSERVATIVE_RASTERIZATION_MODE_OFF;
    psoDesc.DepthStencilState.DepthEnable = FALSE;
    psoDesc.DepthStencilState.StencilEnable = FALSE;
    psoDesc.PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
    psoDesc.NumRenderTargets = 1;
    psoDesc.RTVFormats[0] = targetFormat;
    psoDesc.SampleDesc.Count = 1;
    ComPtr<ID3D12PipelineState> pipeline;
    hr = device->CreateGraphicsPipelineState(&psoDesc, IID_PPV_ARGS(&pipeline));
    if (FAILED(hr)) {
        result.note = "graphics_pso_create:" + hr_string(hr);
        return result;
    }
    result.pipelineState = true;

    D3D12_HEAP_PROPERTIES defaultHeap{};
    defaultHeap.Type = D3D12_HEAP_TYPE_DEFAULT;
    defaultHeap.CreationNodeMask = 1;
    defaultHeap.VisibleNodeMask = 1;
    D3D12_RESOURCE_DESC textureDesc{};
    textureDesc.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    textureDesc.Width = width;
    textureDesc.Height = height;
    textureDesc.DepthOrArraySize = 1;
    textureDesc.MipLevels = 1;
    textureDesc.Format = targetFormat;
    textureDesc.SampleDesc.Count = 1;
    textureDesc.Layout = D3D12_TEXTURE_LAYOUT_UNKNOWN;
    textureDesc.Flags = D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
    D3D12_CLEAR_VALUE clearValue{};
    clearValue.Format = targetFormat;
    clearValue.Color[0] = 0.0f;
    clearValue.Color[1] = 0.0f;
    clearValue.Color[2] = 0.0f;
    clearValue.Color[3] = 1.0f;
    ComPtr<ID3D12Resource> renderTarget;
    hr = device->CreateCommittedResource(&defaultHeap, D3D12_HEAP_FLAG_NONE,
        &textureDesc, D3D12_RESOURCE_STATE_RENDER_TARGET, &clearValue,
        IID_PPV_ARGS(&renderTarget));
    if (FAILED(hr)) {
        result.note = "render_target_create:" + hr_string(hr);
        return result;
    }

    D3D12_DESCRIPTOR_HEAP_DESC rtvHeapDesc{};
    rtvHeapDesc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_RTV;
    rtvHeapDesc.NumDescriptors = 1;
    ComPtr<ID3D12DescriptorHeap> rtvHeap;
    hr = device->CreateDescriptorHeap(&rtvHeapDesc, IID_PPV_ARGS(&rtvHeap));
    if (FAILED(hr)) {
        result.note = "rtv_heap_create:" + hr_string(hr);
        return result;
    }
    device->CreateRenderTargetView(renderTarget.Get(), nullptr,
        rtvHeap->GetCPUDescriptorHandleForHeapStart());

    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
    UINT rows = 0;
    UINT64 rowSize = 0;
    UINT64 totalBytes = 0;
    device->GetCopyableFootprints(&textureDesc, 0, 1, 0,
        &footprint, &rows, &rowSize, &totalBytes);
    D3D12_HEAP_PROPERTIES readbackHeap{};
    readbackHeap.Type = D3D12_HEAP_TYPE_READBACK;
    readbackHeap.CreationNodeMask = 1;
    readbackHeap.VisibleNodeMask = 1;
    D3D12_RESOURCE_DESC bufferDesc{};
    bufferDesc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    bufferDesc.Width = totalBytes;
    bufferDesc.Height = 1;
    bufferDesc.DepthOrArraySize = 1;
    bufferDesc.MipLevels = 1;
    bufferDesc.SampleDesc.Count = 1;
    bufferDesc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    ComPtr<ID3D12Resource> readback;
    hr = device->CreateCommittedResource(&readbackHeap, D3D12_HEAP_FLAG_NONE,
        &bufferDesc, D3D12_RESOURCE_STATE_COPY_DEST, nullptr,
        IID_PPV_ARGS(&readback));
    if (FAILED(hr)) {
        result.note = "readback_create:" + hr_string(hr);
        return result;
    }

    ComPtr<ID3D12CommandAllocator> allocator;
    ComPtr<ID3D12GraphicsCommandList> list;
    hr = device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,
        IID_PPV_ARGS(&allocator));
    if (FAILED(hr)) {
        result.note = "allocator_create:" + hr_string(hr);
        return result;
    }
    hr = device->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT,
        allocator.Get(), pipeline.Get(), IID_PPV_ARGS(&list));
    if (FAILED(hr)) {
        result.note = "command_list_create:" + hr_string(hr);
        return result;
    }
    const auto rtv = rtvHeap->GetCPUDescriptorHandleForHeapStart();
    const FLOAT clear[4] = {0.0f, 0.0f, 0.0f, 1.0f};
    list->OMSetRenderTargets(1, &rtv, FALSE, nullptr);
    list->ClearRenderTargetView(rtv, clear, 0, nullptr);
    D3D12_VIEWPORT viewport{0.0f, 0.0f, static_cast<float>(width),
        static_cast<float>(height), 0.0f, 1.0f};
    D3D12_RECT scissor{0, 0, static_cast<LONG>(width), static_cast<LONG>(height)};
    list->RSSetViewports(1, &viewport);
    list->RSSetScissorRects(1, &scissor);
    list->SetGraphicsRootSignature(rootSignature.Get());
    list->SetPipelineState(pipeline.Get());
    list->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    list->DrawInstanced(3, 1, 0, 0);
    result.drawExecuted = true;

    D3D12_RESOURCE_BARRIER barrier{};
    barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Transition.pResource = renderTarget.Get();
    barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_RENDER_TARGET;
    barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
    list->ResourceBarrier(1, &barrier);
    D3D12_TEXTURE_COPY_LOCATION dst{};
    dst.pResource = readback.Get();
    dst.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
    dst.PlacedFootprint = footprint;
    D3D12_TEXTURE_COPY_LOCATION src{};
    src.pResource = renderTarget.Get();
    src.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    src.SubresourceIndex = 0;
    list->CopyTextureRegion(&dst, 0, 0, 0, &src, nullptr);
    hr = list->Close();
    if (FAILED(hr)) {
        result.note = "command_list_close:" + hr_string(hr);
        return result;
    }
    ID3D12CommandList* lists[] = {list.Get()};
    queue->ExecuteCommandLists(1, lists);

    ComPtr<ID3D12Fence> fence;
    hr = device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence));
    if (FAILED(hr)) {
        result.note = "fence_create:" + hr_string(hr);
        return result;
    }
    HANDLE eventHandle = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    if (!eventHandle) {
        result.note = "event_creation_failed";
        return result;
    }
    hr = queue->Signal(fence.Get(), 1);
    const bool completed = SUCCEEDED(hr) && wait_for_fence(fence.Get(), 1, eventHandle);
    CloseHandle(eventHandle);
    if (!completed) {
        result.note = "render_fence_wait_failed";
        return result;
    }

    const D3D12_RANGE readRange{0, static_cast<SIZE_T>(totalBytes)};
    std::uint8_t* pixels = nullptr;
    hr = readback->Map(0, &readRange, reinterpret_cast<void**>(&pixels));
    if (FAILED(hr)) {
        result.note = "render_readback_map:" + hr_string(hr);
        return result;
    }
    const size_t pixelOffset = static_cast<size_t>(height / 2) * footprint.Footprint.RowPitch
        + static_cast<size_t>(width / 2) * 4;
    const bool pixelMatches = pixels[pixelOffset] == 255 &&
        pixels[pixelOffset + 1] == 0 && pixels[pixelOffset + 2] == 0 &&
        pixels[pixelOffset + 3] == 255;
    const D3D12_RANGE noWrite{0, 0};
    readback->Unmap(0, &noWrite);
    result.success = pixelMatches;
    result.note = pixelMatches ? "hlsl_pso_draw_readback_pixel_verified"
                               : "render_readback_pixel_mismatch";
    return result;
}

int main(int argc, char** argv) {
    bool includeSoftware = false;
    for (int i = 1; i < argc; ++i) {
        if (std::string(argv[i]) == "--include-software") includeSoftware = true;
        else if (std::string(argv[i]) != "--json") {
            std::cerr << "Usage: orion-d3d12-probe [--json] [--include-software]\n";
            return 2;
        }
    }

    ComPtr<IDXGIFactory6> factory;
    HRESULT hr = CreateDXGIFactory2(0, IID_PPV_ARGS(&factory));
    if (FAILED(hr)) {
        std::cout << "{\"schema_version\":1,\"probe\":\"d3d12\",\"available\":false,"
                  << "\"stage\":\"create_dxgi_factory\",\"hresult\":\""
                  << hr_string(hr) << "\"}\n";
        return 1;
    }

    std::vector<std::string> adapterReports;
    UINT adapterIndex = 0;
    UINT hardwareDevices = 0;
    while (true) {
        ComPtr<IDXGIAdapter1> adapter;
        hr = factory->EnumAdapters1(adapterIndex++, &adapter);
        if (hr == DXGI_ERROR_NOT_FOUND) break;
        if (FAILED(hr)) continue;

        DXGI_ADAPTER_DESC1 desc{};
        if (FAILED(adapter->GetDesc1(&desc))) continue;
        const bool software = (desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) != 0;
        if (software && !includeSoftware) continue;

        ComPtr<ID3D12Device> device;
        hr = D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_11_0,
                               IID_PPV_ARGS(&device));
        if (FAILED(hr)) {
            std::ostringstream item;
            item << "{\"name\":\"" << json_escape(narrow(desc.Description))
                 << "\",\"software\":" << (software ? "true" : "false")
                 << ",\"d3d12_device\":false,\"device_creation_hresult\":\""
                 << hr_string(hr) << "\"}";
            adapterReports.push_back(item.str());
            continue;
        }
        if (!software) ++hardwareDevices;

        DXGI_QUERY_VIDEO_MEMORY_INFO localMemory{};
        DXGI_QUERY_VIDEO_MEMORY_INFO nonLocalMemory{};
        bool localMemoryAvailable = false;
        bool nonLocalMemoryAvailable = false;
        ComPtr<IDXGIAdapter3> adapter3;
        if (SUCCEEDED(adapter.As(&adapter3))) {
            localMemoryAvailable = SUCCEEDED(adapter3->QueryVideoMemoryInfo(
                0, DXGI_MEMORY_SEGMENT_GROUP_LOCAL, &localMemory));
            nonLocalMemoryAvailable = SUCCEEDED(adapter3->QueryVideoMemoryInfo(
                0, DXGI_MEMORY_SEGMENT_GROUP_NON_LOCAL, &nonLocalMemory));
        }

        std::string featureLevel = "unknown";
        const std::array<D3D_FEATURE_LEVEL, 5> levels = {
            D3D_FEATURE_LEVEL_12_2, D3D_FEATURE_LEVEL_12_1,
            D3D_FEATURE_LEVEL_12_0, D3D_FEATURE_LEVEL_11_1,
            D3D_FEATURE_LEVEL_11_0
        };
        D3D12_FEATURE_DATA_FEATURE_LEVELS levelData{};
        levelData.NumFeatureLevels = static_cast<UINT>(levels.size());
        levelData.pFeatureLevelsRequested = levels.data();
        if (SUCCEEDED(device->CheckFeatureSupport(D3D12_FEATURE_FEATURE_LEVELS,
                &levelData, sizeof(levelData)))) {
            featureLevel = feature_level_name(levelData.MaxSupportedFeatureLevel);
        }

        std::string shaderModel = "unknown";
        const std::array<D3D_SHADER_MODEL, 8> shaderModels = {
            D3D_SHADER_MODEL_6_7, D3D_SHADER_MODEL_6_6,
            D3D_SHADER_MODEL_6_5, D3D_SHADER_MODEL_6_4,
            D3D_SHADER_MODEL_6_3, D3D_SHADER_MODEL_6_2,
            D3D_SHADER_MODEL_6_1, D3D_SHADER_MODEL_6_0
        };
        for (const auto model : shaderModels) {
            D3D12_FEATURE_DATA_SHADER_MODEL shaderData{model};
            if (SUCCEEDED(device->CheckFeatureSupport(D3D12_FEATURE_SHADER_MODEL,
                    &shaderData, sizeof(shaderData)))) {
                shaderModel = shader_model_name(shaderData.HighestShaderModel);
                break;
            }
        }

        std::string bindingTier = "unknown";
        D3D12_FEATURE_DATA_D3D12_OPTIONS options{};
        if (SUCCEEDED(device->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONS,
                &options, sizeof(options)))) {
            switch (options.ResourceBindingTier) {
            case D3D12_RESOURCE_BINDING_TIER_1: bindingTier = "1"; break;
            case D3D12_RESOURCE_BINDING_TIER_2: bindingTier = "2"; break;
            case D3D12_RESOURCE_BINDING_TIER_3: bindingTier = "3"; break;
            default: break;
            }
        }

        bool waveOps = false;
        UINT waveLaneMin = 0;
        UINT waveLaneMax = 0;
        UINT totalLaneCount = 0;
        bool int64ShaderOps = false;
        bool expandedComputeStates = false;
        D3D12_FEATURE_DATA_D3D12_OPTIONS1 options1{};
        const bool options1Available = SUCCEEDED(device->CheckFeatureSupport(
            D3D12_FEATURE_D3D12_OPTIONS1, &options1, sizeof(options1)));
        if (options1Available) {
            waveOps = options1.WaveOps != FALSE;
            waveLaneMin = options1.WaveLaneCountMin;
            waveLaneMax = options1.WaveLaneCountMax;
            totalLaneCount = options1.TotalLaneCount;
            int64ShaderOps = options1.Int64ShaderOps != FALSE;
            expandedComputeStates = options1.ExpandedComputeResourceStates != FALSE;
        }

        D3D12_FEATURE_DATA_FORMAT_SUPPORT rgba8Support{};
        rgba8Support.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
        const bool rgba8FormatQueryAvailable = SUCCEEDED(device->CheckFeatureSupport(
            D3D12_FEATURE_FORMAT_SUPPORT, &rgba8Support, sizeof(rgba8Support)));

        const std::array<DXGI_FORMAT, 7> queriedFormats = {
            DXGI_FORMAT_R8G8B8A8_UNORM, DXGI_FORMAT_B8G8R8A8_UNORM,
            DXGI_FORMAT_R16G16B16A16_FLOAT, DXGI_FORMAT_R32_FLOAT,
            DXGI_FORMAT_D32_FLOAT, DXGI_FORMAT_BC1_UNORM, DXGI_FORMAT_BC7_UNORM
        };
        std::vector<std::string> formatReports;
        for (const auto format : queriedFormats)
            formatReports.push_back(query_format_support(device.Get(), format));

        D3D12_FEATURE_DATA_D3D12_OPTIONS5 options5{};
        const bool options5Available = SUCCEEDED(device->CheckFeatureSupport(
            D3D12_FEATURE_D3D12_OPTIONS5, &options5, sizeof(options5)));
        std::string raytracingTier = "unknown";
        if (options5Available) {
            switch (options5.RaytracingTier) {
            case D3D12_RAYTRACING_TIER_NOT_SUPPORTED: raytracingTier = "not_supported"; break;
            case D3D12_RAYTRACING_TIER_1_0: raytracingTier = "1_0"; break;
            case D3D12_RAYTRACING_TIER_1_1: raytracingTier = "1_1"; break;
            default: break;
            }
        }

        D3D12_FEATURE_DATA_D3D12_OPTIONS7 options7{};
        const bool options7Available = SUCCEEDED(device->CheckFeatureSupport(
            D3D12_FEATURE_D3D12_OPTIONS7, &options7, sizeof(options7)));
        std::string meshShaderTier = "unknown";
        std::string samplerFeedbackTier = "unknown";
        if (options7Available) {
            switch (options7.MeshShaderTier) {
            case D3D12_MESH_SHADER_TIER_NOT_SUPPORTED: meshShaderTier = "not_supported"; break;
            case D3D12_MESH_SHADER_TIER_1: meshShaderTier = "1"; break;
            default: break;
            }
            switch (options7.SamplerFeedbackTier) {
            case D3D12_SAMPLER_FEEDBACK_TIER_NOT_SUPPORTED: samplerFeedbackTier = "not_supported"; break;
            case D3D12_SAMPLER_FEEDBACK_TIER_0_9: samplerFeedbackTier = "0_9"; break;
            case D3D12_SAMPLER_FEEDBACK_TIER_1_0: samplerFeedbackTier = "1_0"; break;
            default: break;
            }
        }

        bool queueFenceTest = false;
        std::string queueError;
        ComPtr<ID3D12CommandQueue> queue;
        D3D12_COMMAND_QUEUE_DESC queueDesc{};
        queueDesc.Type = D3D12_COMMAND_LIST_TYPE_DIRECT;
        hr = device->CreateCommandQueue(&queueDesc, IID_PPV_ARGS(&queue));
        if (SUCCEEDED(hr)) {
            ComPtr<ID3D12Fence> fence;
            hr = device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence));
            if (SUCCEEDED(hr)) {
                HANDLE eventHandle = CreateEventW(nullptr, FALSE, FALSE, nullptr);
                if (eventHandle) {
                    constexpr UINT64 signalValue = 1;
                    hr = queue->Signal(fence.Get(), signalValue);
                    queueFenceTest = SUCCEEDED(hr) &&
                        wait_for_fence(fence.Get(), signalValue, eventHandle);
                    if (!queueFenceTest) queueError = "signal_or_wait_failed";
                    CloseHandle(eventHandle);
                } else queueError = "create_event_failed";
            } else queueError = "create_fence_failed:" + hr_string(hr);
        } else queueError = "create_command_queue_failed:" + hr_string(hr);

        const ResourceSmokeResult resourceSmoke = queue ? run_resource_copy_smoke_test(device.Get(), queue.Get()) : ResourceSmokeResult{false, "queue_unavailable"};
        const BindingSmokeResult bindingSmoke = run_binding_smoke_test(device.Get());
        const RenderSmokeResult renderSmoke = queue ? run_render_smoke_test(device.Get(), queue.Get()) : RenderSmokeResult{};
        std::ostringstream item;
        item << "{\"name\":\"" << json_escape(narrow(desc.Description))
             << "\",\"vendor_id\":" << desc.VendorId
             << ",\"device_id\":" << desc.DeviceId
             << ",\"software\":" << (software ? "true" : "false")
             << ",\"dedicated_video_memory_bytes\":" << desc.DedicatedVideoMemory
             << ",\"d3d12_device\":true"
             << ",\"feature_level\":\"" << featureLevel << "\""
             << ",\"shader_model\":\"" << shaderModel << "\""
             << ",\"resource_binding_tier\":\"" << bindingTier << "\""
             << ",\"options1_query_available\":" << (options1Available ? "true" : "false")
             << ",\"wave_ops\":" << (options1Available ? (waveOps ? "true" : "false") : "null")
             << ",\"wave_lane_count_min\":" << (options1Available ? std::to_string(waveLaneMin) : "null")
             << ",\"wave_lane_count_max\":" << (options1Available ? std::to_string(waveLaneMax) : "null")
             << ",\"total_lane_count\":" << (options1Available ? std::to_string(totalLaneCount) : "null")
             << ",\"int64_shader_ops\":" << (options1Available ? (int64ShaderOps ? "true" : "false") : "null")
             << ",\"expanded_compute_resource_states\":" << (options1Available ? (expandedComputeStates ? "true" : "false") : "null")
             << ",\"rgba8_format_query_available\":" << (rgba8FormatQueryAvailable ? "true" : "false")
             << ",\"rgba8_support1\":" << (rgba8FormatQueryAvailable ? std::to_string(rgba8Support.Support1) : "null")
             << ",\"rgba8_support2\":" << (rgba8FormatQueryAvailable ? std::to_string(rgba8Support.Support2) : "null")
             << ",\"formats\":[";
        for (size_t formatIndex = 0; formatIndex < formatReports.size(); ++formatIndex) {
            if (formatIndex) item << ",";
            item << formatReports[formatIndex];
        }
        item << "]"
             << ",\"video_memory\":{"
             << "\"local\":{\"query_available\":" << (localMemoryAvailable ? "true" : "false")
             << ",\"budget_bytes\":" << (localMemoryAvailable ? std::to_string(localMemory.Budget) : "null")
             << ",\"current_usage_bytes\":" << (localMemoryAvailable ? std::to_string(localMemory.CurrentUsage) : "null")
             << ",\"available_for_reservation_bytes\":" << (localMemoryAvailable ? std::to_string(localMemory.AvailableForReservation) : "null")
             << "},\"non_local\":{\"query_available\":" << (nonLocalMemoryAvailable ? "true" : "false")
             << ",\"budget_bytes\":" << (nonLocalMemoryAvailable ? std::to_string(nonLocalMemory.Budget) : "null")
             << ",\"current_usage_bytes\":" << (nonLocalMemoryAvailable ? std::to_string(nonLocalMemory.CurrentUsage) : "null")
             << ",\"available_for_reservation_bytes\":" << (nonLocalMemoryAvailable ? std::to_string(nonLocalMemory.AvailableForReservation) : "null")
             << "}}"
             << ",\"options5_query_available\":" << (options5Available ? "true" : "false")
             << ",\"raytracing_tier\":\"" << (options5Available ? raytracingTier : "unknown") << "\""
             << ",\"options7_query_available\":" << (options7Available ? "true" : "false")
             << ",\"mesh_shader_tier\":\"" << (options7Available ? meshShaderTier : "unknown") << "\""
             << ",\"sampler_feedback_tier\":\"" << (options7Available ? samplerFeedbackTier : "unknown") << "\""
             << ",\"direct_queue_fence_test\":" << (queueFenceTest ? "true" : "false")
             << ",\"queue_test_note\":\"" << json_escape(queueError) << "\""
             << ",\"resource_copy_smoke_test\":" << (resourceSmoke.success ? "true" : "false")
             << ",\"resource_copy_smoke_note\":\"" << json_escape(resourceSmoke.note) << "\""
             << ",\"root_signature_smoke_test\":" << (bindingSmoke.rootSignatureCreated ? "true" : "false")
             << ",\"resource_descriptor_heap_smoke_test\":" << (bindingSmoke.resourceHeapCreated ? "true" : "false")
             << ",\"sampler_descriptor_heap_smoke_test\":" << (bindingSmoke.samplerHeapCreated ? "true" : "false")
             << ",\"resource_descriptor_increment\":" << bindingSmoke.resourceDescriptorIncrement
             << ",\"sampler_descriptor_increment\":" << bindingSmoke.samplerDescriptorIncrement
             << ",\"binding_smoke_note\":\"" << json_escape(bindingSmoke.note) << "\""
             << ",\"render_smoke_test\":" << (renderSmoke.success ? "true" : "false")
             << ",\"render_shader_compile\":" << (renderSmoke.shaderCompile ? "true" : "false")
             << ",\"render_root_signature\":" << (renderSmoke.rootSignature ? "true" : "false")
             << ",\"render_pipeline_state\":" << (renderSmoke.pipelineState ? "true" : "false")
             << ",\"render_draw_executed\":" << (renderSmoke.drawExecuted ? "true" : "false")
             << ",\"render_smoke_note\":\"" << json_escape(renderSmoke.note) << "\"}";
        adapterReports.push_back(item.str());
    }

    std::cout << "{\"schema_version\":1,\"probe\":\"orion_d3d12_probe\","
              << "\"available\":" << (hardwareDevices ? "true" : "false")
              << ",\"hardware_d3d12_adapters\":" << hardwareDevices
              << ",\"software_adapters_included\":" << (includeSoftware ? "true" : "false")
              << ",\"adapters\":[";
    for (size_t i = 0; i < adapterReports.size(); ++i) {
        if (i) std::cout << ",";
        std::cout << adapterReports[i];
    }
    std::cout << "],\"limitations\":["
              << "\"Queries public Windows D3D12 driver capabilities only.\","
              << "\"Does not emulate Xbox D3D12.x or establish game compatibility.\","
              << "\"No settings, drivers, registry values, or files are modified.\"]}\n";
    return hardwareDevices ? 0 : 3;
}
