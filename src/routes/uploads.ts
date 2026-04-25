import fs from "node:fs";
import path from "node:path";
import { Router } from "express";
import multer from "multer";
import { requireAuth } from "../middleware/auth";
import { asyncHandler, ok } from "../utils/http";

const uploadDir = path.resolve(process.cwd(), "uploads");
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadDir),
  filename: (_req, file, cb) => {
    const safeName = `${Date.now()}-${file.originalname.replace(/\s+/g, "-")}`;
    cb(null, safeName);
  },
});

const upload = multer({ storage });

const router = Router();

router.use(requireAuth);

router.post(
  "/",
  upload.single("file"),
  asyncHandler(async (req, res) => {
    return ok(res, {
      success: true,
      file: req.file
        ? {
            filename: req.file.filename,
            path: `/uploads/${req.file.filename}`,
            mimetype: req.file.mimetype,
            size: req.file.size,
          }
        : null,
    });
  }),
);

export default router;
