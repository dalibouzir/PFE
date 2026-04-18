"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { useCreateProduct, useDeleteProduct, useProducts, useUpdateProduct } from "@/hooks/useProducts";
import type { Product, ProductCreate } from "@/lib/api/types";

export default function ProduitsPage() {
  const { data: products = [] } = useProducts();
  const createProduct = useCreateProduct();
  const updateProduct = useUpdateProduct();
  const deleteProduct = useDeleteProduct();
  const [formOpen, setFormOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const { register, handleSubmit, reset, formState } = useForm<ProductCreate>({
    defaultValues: { name: "", category: "", unit: "", quality_grade: "" },
  });

  const openCreateForm = () => {
    setEditingProduct(null);
    reset({ name: "", category: "", unit: "", quality_grade: "" });
    setFormError(null);
    setFormOpen(true);
  };

  const openEditForm = (product: Product) => {
    setEditingProduct(product);
    reset({
      name: product.name,
      category: product.category,
      unit: product.unit,
      quality_grade: product.quality_grade ?? "",
    });
    setFormError(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setFormError(null);
  };

  const submitProduct = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const payload: ProductCreate = {
        name: values.name.trim(),
        category: values.category.trim(),
        unit: values.unit.trim(),
        quality_grade: values.quality_grade?.trim() || null,
      };

      if (editingProduct) {
        await updateProduct.mutateAsync({ id: editingProduct.id, payload });
      } else {
        await createProduct.mutateAsync(payload);
      }
      closeForm();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer le produit.");
    }
  });

  const handleDeleteProduct = async (product: Product) => {
    if (!window.confirm("Supprimer ce produit ?")) return;
    try {
      await deleteProduct.mutateAsync(product.id);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible de supprimer le produit.");
    }
  };

  return (
    <main>
      <PageIntro title="Produits" subtitle="Catalogue produits synchronise avec l'API." />

      <div className="mb-4 flex justify-end">
        <button
          type="button"
          onClick={openCreateForm}
          className="soft-focus rounded-xl bg-[var(--primary)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]"
        >
          Nouveau produit
        </button>
      </div>

      {products.length === 0 ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "80ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucun produit enregistre.</p>
        </section>
      ) : (
        <section className="grid gap-4 lg:grid-cols-3">
          {products.map((item, index) => (
            <article key={item.id} className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: `${index * 60}ms` }}>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-[var(--text)]">{item.name}</h3>
                <span className="rounded-full bg-[var(--green-200)] px-2 py-1 text-[11px] font-semibold text-[var(--muted)]">
                  {item.unit}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="rounded-xl bg-[var(--surface-soft)] p-3">
                  <p className="text-[11px] text-[var(--muted)]">Categorie</p>
                  <p className="font-semibold text-[var(--text)]">{item.category}</p>
                </div>
                <div className="rounded-xl bg-[var(--surface-soft)] p-3">
                  <p className="text-[11px] text-[var(--muted)]">Grade</p>
                  <p className="font-semibold text-[var(--text)]">{item.quality_grade ?? "-"}</p>
                </div>
              </div>

              <p className="mt-4 text-xs text-[var(--muted)]">Produit ID: {item.id.slice(0, 8)}</p>

              <div className="mt-3 flex items-center gap-2">
                <button
                  type="button"
                  className="text-xs font-semibold text-[var(--green-700)] hover:underline"
                  onClick={() => openEditForm(item)}
                >
                  Modifier
                </button>
                <button
                  type="button"
                  className="text-xs font-semibold text-[#a34141] hover:underline"
                  onClick={() => handleDeleteProduct(item)}
                >
                  Supprimer
                </button>
              </div>
            </article>
          ))}
        </section>
      )}

      <LiquidGlassModal
        open={formOpen}
        onClose={closeForm}
        title={editingProduct ? "Modifier produit" : "Nouveau produit"}
        subtitle="Les produits sont rattaches a la cooperative."
        size="md"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus rounded-xl border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--text)]" onClick={closeForm}>
              Annuler
            </button>
            <button type="submit" form="product-form" className="soft-focus rounded-xl bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        }
      >
        <form id="product-form" onSubmit={submitProduct} className="space-y-3">
          <label className="block text-sm font-medium text-[var(--text)]">
            Nom produit
            <input
              {...register("name", { required: "Nom requis." })}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="Mangue sechee"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Categorie
            <input
              {...register("category", { required: "Categorie requise." })}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="Fruit transforme"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Unite
            <input
              {...register("unit", { required: "Unite requise." })}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="kg"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Grade (optionnel)
            <input
              {...register("quality_grade")}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="A"
            />
          </label>
          {formError && (
            <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
              {formError}
            </p>
          )}
        </form>
      </LiquidGlassModal>
    </main>
  );
}
