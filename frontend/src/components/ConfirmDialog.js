import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "./ui/alert-dialog";

export const ConfirmDialog = ({ open, onConfirm, onCancel, title, description, confirmText = "Löschen", variant = "destructive" }) => {
  return (
    <AlertDialog open={open} onOpenChange={(v) => !v && onCancel()}>
      <AlertDialogContent className="bg-white" data-testid="confirm-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle className="text-gray-900">{title}</AlertDialogTitle>
          <AlertDialogDescription className="text-gray-500">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancel} className="border-gray-300" data-testid="confirm-cancel-btn">
            Abbrechen
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className={variant === "destructive" ? "bg-red-600 hover:bg-red-700 text-white" : "bg-fuchsia-600 hover:bg-fuchsia-700 text-white"}
            data-testid="confirm-action-btn"
          >
            {confirmText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
