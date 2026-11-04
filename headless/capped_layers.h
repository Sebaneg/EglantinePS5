// SPDX-License-Identifier: GPL-3.0-or-later
// Texture arrays made with fewer layers than the game asked for.
//
// A Switch 2 title asked for an 8192x8192 BC6H array of 68 layers (4.5G texels, over 5 GB). That is
// too large to back, so Eden makes it as an unbacked sparse image, but the console's driver refuses
// sparse images of that size: 34 layers were refused and 17 accepted. The image was then refused
// outright and the session ended (VK_ERROR_OUT_OF_DEVICE_MEMORY). Such an image is now made with one
// layer, six for a cube (tools/prepare-vulkan-port.py, CreateUnbackedImage), and the views of it are
// kept inside those layers (vk_texture_cache.cpp, ImageView). Nothing is bound to an unbacked image
// and nothing is uploaded to it, so the layers left out read the same as the others. Made with the
// 17 layers the driver took, it held 1.5 GB of GPU address space, and the driver could no longer
// map the next 100 MB images.
#pragma once
#include <cstdint>
#include <mutex>
#include <unordered_map>

namespace Eden::CappedLayers {

struct Capped {
    std::uint32_t asked;
    std::uint32_t made;
};

inline std::mutex capped_lock;
inline std::unordered_map<std::uintptr_t, Capped> capped_images;

template <typename Handle>
inline std::uintptr_t Key(Handle image) {
    return reinterpret_cast<std::uintptr_t>(image);
}

template <typename Handle>
inline void Remember(Handle image, std::uint32_t asked, std::uint32_t made) {
    const std::scoped_lock lock{capped_lock};
    capped_images[Key(image)] = {asked, made};
}

template <typename Handle>
inline void Forget(Handle image) {
    if (!image) return;
    const std::scoped_lock lock{capped_lock};
    capped_images.erase(Key(image));
}

// The layers the image was made with; 0 when it has all it asked for. `asked` (the layers of the
// image as the texture cache knows it) must match: a handle given out again to another image,
// whose earlier owner was replaced without being forgotten, is not taken for the capped one.
template <typename Handle>
inline std::uint32_t Of(Handle image, std::uint32_t asked) {
    if (!image) return 0;
    const std::scoped_lock lock{capped_lock};
    const auto found = capped_images.find(Key(image));
    if (found == capped_images.end()) return 0;
    if (found->second.asked != asked) {
        capped_images.erase(found);
        return 0;
    }
    return found->second.made;
}

// Keeps a view's layers inside the `made` layers of its image, in whole groups of `multiple`
// (6 for cube views). A range that cannot fit is left as it is.
template <typename Range>
inline void Clamp(Range& range, std::uint32_t made, std::uint32_t multiple, std::uint32_t remaining) {
    if (made < multiple || multiple == 0) return;
    if (range.baseArrayLayer + multiple > made) {
        range.baseArrayLayer = (made / multiple - 1) * multiple;
    }
    const std::uint32_t room = (made - range.baseArrayLayer) / multiple * multiple;
    if (range.layerCount != remaining && range.layerCount > room) {
        range.layerCount = room;
    }
}

} // namespace Eden::CappedLayers
