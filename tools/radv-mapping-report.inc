static struct radv_ps5_granules radv_ps5_region;

/* Why a mapping was refused while the pool had memory (Mario Kart World: 0x8002000C with 1.2 GB
 * free): what is left of the device-memory region, and how many mappings the process holds, walked
 * with the kernel's virtual query. Printed for the first two refusals only. */
/* libkernel's query record, as PS5_Vulkan's tooling/gpu-broker/client.c reads it. */
struct radv_ps5_query_info {
   uint64_t start;
   uint64_t end;
   uint64_t offset;
   int32_t protection;
   int32_t memory_type;
   uint8_t flags; /* bit 0 flexible, bit 1 direct, bit 2 stack, bit 3 pooled, bit 4 committed */
   char name[32];
   uint8_t padding[7];
};
_Static_assert(sizeof(struct radv_ps5_query_info) == 72, "libkernel query record");
/* libkernel's; not weak: headless/check_package.py refuses an unresolved weak import. */
int sceKernelVirtualQuery(const void *address, int flags, void *info, size_t size);

static void
radv_ps5_report_space(void)
{
   static int reports;
   if (p_atomic_inc_return(&reports) > 2)
      return;
   uint32_t free_granules = 0, run = 0, longest = 0;
   simple_mtx_lock(&radv_ps5_region.lock);
   for (uint32_t i = 0; i < radv_ps5_region.count; i++) {
      if (radv_ps5_region.used[i / 64] & (UINT64_C(1) << (i % 64))) {
         run = 0;
      } else {
         free_granules++;
         if (++run > longest)
            longest = run;
      }
   }
   const uint32_t granules = radv_ps5_region.count;
   simple_mtx_unlock(&radv_ps5_region.lock);
   uint32_t mappings = 0, direct = 0, flexible = 0;
   uint64_t mapped = 0, direct_bytes = 0;
   struct radv_ps5_query_info info;
   const void *at = NULL;
   while (mappings < 1000000) {
      memset(&info, 0, sizeof(info));
      if (sceKernelVirtualQuery(at, 1 /* the next mapping from `at` */, &info, sizeof(info)) != 0 ||
          info.end <= (uint64_t)(uintptr_t)at)
         break;
      mappings++;
      mapped += info.end - info.start;
      if (info.flags & 2) {
         direct++;
         direct_bytes += info.end - info.start;
      }
      if (info.flags & 1)
         flexible++;
      at = (const void *)(uintptr_t)info.end;
   }
   fprintf(stderr,
           "radv/ps5: device region %u of %u 2 MiB granules free (longest run %u); the process holds %u "
           "mappings (%llu MiB), %u of direct memory (%llu MiB), %u flexible\n",
           free_granules, granules, longest, mappings, (unsigned long long)(mapped >> 20), direct,
           (unsigned long long)(direct_bytes >> 20), flexible);
}
