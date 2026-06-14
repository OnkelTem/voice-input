#include "whisper.h"

int whisper_full_ptr(
        struct whisper_context * ctx,
        struct whisper_full_params * params,
        const float * samples,
        int n_samples) {
    return whisper_full(ctx, *params, samples, n_samples);
}
