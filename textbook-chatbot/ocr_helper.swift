import Vision
import Foundation
import AppKit

func recognizeText(imagePath: String) -> String {
    guard let image = NSImage(contentsOfFile: imagePath),
          let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        fputs("Error: Cannot load image at \(imagePath)\n", stderr)
        return ""
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["ja-JP", "en-US"]

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    do {
        try handler.perform([request])
    } catch {
        fputs("Error: \(error)\n", stderr)
        return ""
    }

    guard let observations = request.results else { return "" }

    let lines = observations.compactMap { obs -> String? in
        guard let candidate = obs.topCandidates(1).first else { return nil }
        return candidate.string
    }

    return lines.joined(separator: "\n")
}

// 引数: <image_path>
let args = CommandLine.arguments
guard args.count == 2 else {
    fputs("Usage: ocr_helper <image_path>\n", stderr)
    exit(1)
}

let text = recognizeText(imagePath: args[1])
print(text)
