#import <AppKit/AppKit.h>
#import <CoreText/CoreText.h>
#import "FontHook.h"

// Loaded only by an explicitly launched, owned test host. No process attachment.
__attribute__((constructor)) static void FontLabStart(void) {
    @autoreleasepool {
        const char *path = getenv("FONTLAB_FONT");
        if (!path) return;
        NSURL *url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:path]];
        CFErrorRef error = NULL;
        if (!CTFontManagerRegisterFontsForURL((__bridge CFURLRef)url, kCTFontManagerScopeProcess, &error)) {
            if (error) CFRelease(error);
            fprintf(stderr, "FontLab injector: registration failed\n");
            return;
        }
        NSArray *descriptors = CFBridgingRelease(CTFontManagerCreateFontDescriptorsFromURL((__bridge CFURLRef)url));
        if (!descriptors.count) return;
        NSString *name = CFBridgingRelease(CTFontDescriptorCopyAttribute((__bridge CTFontDescriptorRef)descriptors[0], kCTFontNameAttribute));
        fprintf(stderr, "FontLab injector: hook=%d\n", FLInstallHook(name));
    }
}
